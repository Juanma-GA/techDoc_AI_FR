"""Optional Mistral synthesis for a saved text comparison."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.comparison_report import ensure_current_report
from app.core.errors import AppError
from app.core.llm_suggester import call_chat
from app.db.session import get_db

from .comparison_schemas import ComparisonSummary, SynthesisIn, SynthesisOut
from .comparisons import get_comparison

router = APIRouter(prefix="/comparisons", tags=["comparisons"])
MAX_SUMMARY_INPUT_CHARS = 100_000


@router.post("/{comparison_id}/synthesis", response_model=SynthesisOut)
def synthesize_comparison(
    comparison_id: uuid.UUID,
    body: SynthesisIn,
    db: Session = Depends(get_db),
) -> SynthesisOut:
    row = get_comparison(comparison_id, db)
    report = ensure_current_report(row, db)
    filenames = {item["index"]: item["filename"] for item in report["documents"]}
    reference_name = filenames[row.reference_index]
    missing_page_lines: list[str] = []
    for comparison in report["comparisons"]:
        reference_only_pages = sorted(
            match["reference_page"]
            for match in comparison["page_alignment"]
            if match["status"] == "reference_only" and match["reference_page"] is not None
        )
        comparison_only_pages = sorted(
            match["comparison_page"]
            for match in comparison["page_alignment"]
            if match["status"] == "comparison_only" and match["comparison_page"] is not None
        )
        if body.language == "fr":
            if reference_only_pages:
                missing_page_lines.append(
                    f"PAGES SANS CORRESPONDANCE | {comparison['filename']} | pages présentes "
                    f"dans la référence mais absentes de ce document : "
                    f"{', '.join(str(page) for page in reference_only_pages)}. Contenu non analysé."
                )
            if comparison_only_pages:
                missing_page_lines.append(
                    f"PAGES SANS CORRESPONDANCE | {comparison['filename']} | pages présentes "
                    f"dans ce document mais absentes de la référence : "
                    f"{', '.join(str(page) for page in comparison_only_pages)}. Contenu non analysé."
                )
        else:
            if reference_only_pages:
                missing_page_lines.append(
                    f"UNMATCHED PAGES | {comparison['filename']} | pages present in the reference "
                    f"but absent from this document: "
                    f"{', '.join(str(page) for page in reference_only_pages)}. Content not analyzed."
                )
            if comparison_only_pages:
                missing_page_lines.append(
                    f"UNMATCHED PAGES | {comparison['filename']} | pages present in this document "
                    f"but absent from the reference: "
                    f"{', '.join(str(page) for page in comparison_only_pages)}. Content not analyzed."
                )

    if body.language == "fr":
        system = (
            "Explique simplement les différences entre des versions de documents techniques. "
            "N'analyse ni ne décris le texte ou la mise en page des pages sans correspondance ; "
            "mentionne uniquement leurs numéros et leur absence. Ne déduis rien qui ne soit pas "
            "présent dans les extraits. Réponds en JSON avec "
            "les champs summary (string), key_changes (array of strings) et impact (string), "
            "en français."
        )
        heading = (
            f"Document de référence : {reference_name}\n"
            "Pages sans correspondance et différences sur les pages correspondantes :\n"
        )
        no_differences = "Aucune différence textuelle détectée."
        omitted_marker = "[D'autres pages ou différences sont omises de l'entrée de synthèse.]"
    else:
        system = (
            "Explain the differences between technical document versions in plain language. "
            "Do not analyze or describe the text or layout of unmatched pages; mention only "
            "their page numbers and absence. Do not infer anything not present in the excerpts. "
            "Respond as JSON with "
            "summary (string), key_changes (array of strings), and impact (string), in English."
        )
        heading = (
            f"Reference document: {reference_name}\n"
            "Unmatched pages and differences on matched pages:\n"
        )
        no_differences = "No text differences were found."
        omitted_marker = "[Additional pages or differences omitted from the AI summary input.]"

    prompt_lines: list[str] = []
    used_chars = 0
    truncated = False

    def append_prompt_line(line: str) -> bool:
        nonlocal used_chars, truncated
        remaining = MAX_SUMMARY_INPUT_CHARS - used_chars
        if len(line) > remaining:
            if remaining > 0:
                prompt_lines.append(line[:remaining])
            truncated = True
            return False
        prompt_lines.append(line)
        used_chars += len(line) + 1
        return True

    for line in missing_page_lines:
        if not append_prompt_line(line):
            break

    if not truncated:
        for comparison in report["comparisons"]:
            for change in comparison["changes"]:
                line = (
                    f"{change['kind']} | {comparison['filename']} | page {change['page']} | "
                    f"{change['text']}"
                )
                if not append_prompt_line(line):
                    break
            if truncated:
                break

    if truncated:
        prompt_lines.append(omitted_marker)

    try:
        raw_summary = call_chat(
            db,
            system,
            heading + ("\n".join(prompt_lines) or no_differences),
            temperature=0.2,
        )
    except AppError as exc:
        if exc.code in {"LLM_DISABLED", "MISTRAL_NOT_CONFIGURED"}:
            row.ai_status = "disabled" if exc.code == "LLM_DISABLED" else "not_configured"
            row.ai_summary_json = None
            row.ai_summary_truncated = False
            db.commit()
            return SynthesisOut(
                ai_status=row.ai_status,
                ai_summary=None,
                ai_summary_truncated=False,
            )
        row.ai_status = "error"
        db.commit()
        raise

    try:
        summary = ComparisonSummary.model_validate_json(raw_summary)
    except ValidationError as exc:
        row.ai_status = "error"
        db.commit()
        raise AppError(
            "COMPARISON_SUMMARY_INVALID",
            "Mistral a retourné une synthèse invalide.",
            status_code=502,
        ) from exc

    row.ai_status = "completed"
    row.ai_summary_json = summary.model_dump_json()
    row.ai_summary_truncated = truncated
    db.commit()
    return SynthesisOut(
        ai_status=row.ai_status,
        ai_summary=summary,
        ai_summary_truncated=truncated,
    )
