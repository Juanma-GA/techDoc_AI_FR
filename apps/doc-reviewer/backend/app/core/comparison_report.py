"""Load and lazily upgrade persisted comparison reports."""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.config import settings
from app.core.comparison_page_alignment import align_pages, combine_page_slots
from app.core.comparison_page_similarity import PAGE_SIMILARITY_THRESHOLD
from app.core.document_comparison import PdfTextLine, extract_pdf_text
from app.core.errors import AppError
from app.core.security import safe_storage_join
from app.db.comparison_models import DocumentComparison

REPORT_SCHEMA_VERSION = 5
ChangeKind = Literal["added", "removed"]


def build_comparison_report(
    paths: list[Path],
    filenames: list[str],
    reference_index: int,
    page_similarity_threshold: float = PAGE_SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    extracted = [extract_pdf_text(path) for path in paths]
    documents = [
        {"index": index, "filename": filenames[index], "page_count": pdf.page_count}
        for index, pdf in enumerate(extracted)
    ]
    comparisons: list[dict[str, Any]] = []
    reference = extracted[reference_index]
    reference_lines_by_page = _lines_by_page(reference.lines)
    for index, candidate in enumerate(extracted):
        if index == reference_index:
            continue
        page_alignment = align_pages(
            reference.pages,
            candidate.pages,
            index,
            page_similarity_threshold,
        )
        candidate_lines_by_page = _lines_by_page(candidate.lines)
        changes: list[dict[str, Any]] = []
        for pair_index, page_match in enumerate(page_alignment):
            if page_match["status"] not in {"aligned", "changed"}:
                continue
            reference_page = page_match["reference_page"]
            comparison_page = page_match["comparison_page"]
            if reference_page is None or comparison_page is None:
                continue
            changes.extend(
                _diff_lines(
                    reference_lines_by_page.get(reference_page, ()),
                    candidate_lines_by_page.get(comparison_page, ()),
                    f"document-{index}-pair-{pair_index}",
                )
            )
        comparisons.append(
            {
                "document_index": index,
                "filename": filenames[index],
                "added_count": sum(change["kind"] == "added" for change in changes),
                "removed_count": sum(change["kind"] == "removed" for change in changes),
                "changes": changes,
                "page_alignment": page_alignment,
            }
        )

    page_slots = combine_page_slots(comparisons)
    for comparison in comparisons:
        for alignment in comparison["page_alignment"]:
            alignment.pop("_sort_key", None)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "reference_index": reference_index,
        "documents": documents,
        "comparisons": comparisons,
        "page_slots": page_slots,
    }


def _diff_lines(
    reference: tuple[PdfTextLine, ...],
    candidate: tuple[PdfTextLine, ...],
    group_prefix: str,
) -> list[dict[str, Any]]:
    matcher = SequenceMatcher(
        a=[line.normalized for line in reference],
        b=[line.normalized for line in candidate],
    )
    changes: list[dict[str, Any]] = []
    change_number = 0
    for operation, ref_start, ref_end, candidate_start, candidate_end in matcher.get_opcodes():
        if operation == "equal":
            continue
        group_id = f"{group_prefix}-change-{change_number}"
        change_number += 1
        if operation in {"delete", "replace"}:
            changes.extend(
                _change("removed", line, group_id) for line in reference[ref_start:ref_end]
            )
        if operation in {"insert", "replace"}:
            changes.extend(
                _change("added", line, group_id)
                for line in candidate[candidate_start:candidate_end]
            )
    return changes


def _lines_by_page(
    lines: tuple[PdfTextLine, ...],
) -> dict[int, tuple[PdfTextLine, ...]]:
    pages: dict[int, list[PdfTextLine]] = {}
    for line in lines:
        pages.setdefault(line.page, []).append(line)
    return {page: tuple(page_lines) for page, page_lines in pages.items()}


def _change(kind: ChangeKind, line: PdfTextLine, group_id: str) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "kind": kind,
        "page": line.page,
        "text": line.text,
        "bbox": {
            "x0": line.bbox[0],
            "y0": line.bbox[1],
            "x1": line.bbox[2],
            "y1": line.bbox[3],
            "page_w": line.page_width,
            "page_h": line.page_height,
            "page_rotation": line.page_rotation,
        },
    }


def ensure_current_report(row: DocumentComparison, db: Session) -> dict[str, Any]:
    try:
        report = json.loads(row.report_json)
    except json.JSONDecodeError as exc:
        raise AppError(
            "COMPARISON_DATA_INVALID",
            "Les résultats enregistrés de cette comparaison sont illisibles.",
            status_code=500,
        ) from exc
    if not isinstance(report, dict):
        raise AppError(
            "COMPARISON_DATA_INVALID",
            "Les résultats enregistrés de cette comparaison sont invalides.",
            status_code=500,
        )
    if report.get("schema_version") == REPORT_SCHEMA_VERSION and isinstance(
        report.get("page_slots"), list
    ):
        return report

    saved_documents = report.get("documents")
    if not isinstance(saved_documents, list) or len(saved_documents) != row.file_count:
        raise AppError(
            "COMPARISON_DATA_INVALID",
            "Les fichiers enregistrés ne correspondent pas aux résultats de cette comparaison.",
            status_code=500,
        )

    paths: list[Path] = []
    filenames: list[str] = []
    for index, item in enumerate(saved_documents):
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise AppError(
                "COMPARISON_DATA_INVALID",
                "Le nom d'un fichier enregistré est invalide.",
                status_code=500,
            )
        path = safe_storage_join(
            Path(settings.storage_dir),
            "comparisons",
            row.id.hex,
            f"document-{index}.pdf",
        )
        if not path.is_file():
            raise AppError(
                "COMPARISON_FILE_MISSING",
                "Un PDF de cette comparaison est introuvable.",
                status_code=404,
            )
        paths.append(path)
        filenames.append(item["filename"])

    current_report = build_comparison_report(paths, filenames, row.reference_index)
    row.report_json = json.dumps(current_report, ensure_ascii=False)
    row.ai_summary_json = None
    row.ai_status = "pending"
    row.ai_summary_truncated = False
    db.commit()
    return current_report
