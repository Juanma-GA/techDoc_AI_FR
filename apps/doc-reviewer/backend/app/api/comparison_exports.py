"""Export annotated comparison PDFs and delete saved comparisons."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.comparison_export import build_commented_pdf
from app.core.comparison_report import ensure_current_report
from app.core.errors import AppError
from app.core.security import safe_filename, safe_storage_join
from app.db.session import get_db

from .comparisons import comparison_dir, comparison_root, get_comparison

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


def _commented_pdf(
    comparison_id: uuid.UUID,
    reference_index: int,
    report: dict,
    comparisons: list[dict],
    language: Literal["fr", "en"],
) -> tuple[bytes, str]:
    if not comparisons:
        raise AppError(
            "COMPARISON_DATA_INVALID",
            "Aucune version comparée n'est disponible pour cet export.",
            status_code=500,
        )
    reference = report["documents"][reference_index]
    path = safe_storage_join(
        comparison_root(),
        comparison_id.hex,
        f"document-{reference_index}.pdf",
    )
    if not path.is_file():
        raise AppError("COMPARISON_FILE_MISSING", "Le PDF de référence est introuvable.", status_code=404)
    content = build_commented_pdf(
        path,
        reference_filename=reference["filename"],
        comparisons=comparisons,
        language=language,
    )
    filename_stem = Path(reference["filename"]).stem
    if len(comparisons) == 1:
        filename_stem += f"_vs_{Path(comparisons[0]['filename']).stem}"
    filename = safe_filename(f"{filename_stem}_diff.pdf")
    return content, filename


def _pdf_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{comparison_id}/export")
def export_comparison(
    comparison_id: uuid.UUID,
    language: Literal["fr", "en"] = Query("fr"),
    db: Session = Depends(get_db),
) -> Response:
    row = get_comparison(comparison_id, db)
    report = ensure_current_report(row, db)
    content, filename = _commented_pdf(
        row.id, row.reference_index, report, report["comparisons"], language
    )
    return _pdf_response(content, filename)


@router.get("/{comparison_id}/export/{document_index}")
def export_comparison_document(
    comparison_id: uuid.UUID,
    document_index: int,
    language: Literal["fr", "en"] = Query("fr"),
    db: Session = Depends(get_db),
) -> Response:
    row = get_comparison(comparison_id, db)
    report = ensure_current_report(row, db)
    comparison = next(
        (entry for entry in report["comparisons"] if entry["document_index"] == document_index),
        None,
    )
    if comparison is None:
        raise AppError("COMPARISON_FILE_NOT_FOUND", "PDF comparé introuvable.", status_code=404)
    content, filename = _commented_pdf(
        row.id, row.reference_index, report, [comparison], language
    )
    return _pdf_response(content, filename)


@router.delete("/{comparison_id}", status_code=204)
def delete_comparison(
    comparison_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    row = get_comparison(comparison_id, db)
    directory = comparison_dir(row.id)
    if directory.exists():
        shutil.rmtree(directory)
    db.delete(row)
    db.commit()
    return Response(status_code=204)
