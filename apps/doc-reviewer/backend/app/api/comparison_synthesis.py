"""Optional Mistral synthesis for a saved text comparison."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.llm_suggester import call_chat
from app.db.session import get_db

from .comparison_schemas import ComparisonSummary, SynthesisIn, SynthesisOut
from .comparisons import get_comparison, load_report

router = APIRouter(prefix="/comparisons", tags=["comparisons"])
MAX_SUMMARY_INPUT_CHARS = 100_000


@router.post("/{comparison_id}/synthesis", response_model=SynthesisOut)
def synthesize_comparison(
    comparison_id: uuid.UUID,
    body: SynthesisIn,
    db: Session = Depends(get_db),
) -> SynthesisOut:
    row = get_comparison(comparison_id, db)
    report = load_report(row)
    change_lines: list[str] = []
    used_chars = 0
    truncated = False
    for comparison in report["comparisons"]:
        for change in comparison["changes"]:
            line = (
                f"{change['kind']} | {comparison['filename']} | page {change['page']} | "
                f"{change['text']}"
            )
            remaining = MAX_SUMMARY_INPUT_CHARS - used_chars
            if len(line) > remaining:
                if remaining > 0:
                    change_lines.append(line[:remaining])
                truncated = True
                break
            change_lines.append(line)
            used_chars += len(line) + 1
        if truncated:
            break
    if truncated:
        change_lines.append("[Additional differences omitted from the AI summary input.]")

    filenames = {item["index"]: item["filename"] for item in report["documents"]}
    reference_name = filenames[row.reference_index]
    if body.language == "fr":
        system = (
            "Explique simplement les différences entre des versions de documents techniques. "
            "Ne déduis rien qui ne soit pas présent dans les extraits. Réponds en JSON avec "
            "les champs summary (string), key_changes (array of strings) et impact (string), "
            "en français."
        )
        heading = f"Document de référence : {reference_name}\nDifférences :\n"
    else:
        system = (
            "Explain the differences between technical document versions in plain language. "
            "Do not infer anything not present in the excerpts. Respond as JSON with "
            "summary (string), key_changes (array of strings), and impact (string), in English."
        )
        heading = f"Reference document: {reference_name}\nDifferences:\n"

    try:
        raw_summary = call_chat(
            db,
            system,
            heading + ("\n".join(change_lines) or "No text differences were found."),
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
