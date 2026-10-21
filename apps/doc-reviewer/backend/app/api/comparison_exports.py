"""Export annotated comparison PDFs and delete saved comparisons."""

from __future__ import annotations

import io
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.comparison_export import build_commented_pdf
from app.core.errors import AppError
from app.core.security import safe_filename, safe_storage_join
from app.db.session import get_db

from .comparisons import comparison_dir, comparison_root, get_comparison, load_report

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


def _commented_pdf(
    comparison_id: uuid.UUID,
    reference_index: int,
    report: dict,
    document_index: int,
    language: Literal["fr", "en"],
) -> tuple[bytes, str]:
    if document_index == reference_index:
        raise AppError(
            "COMPARISON_REFERENCE_EXPORT",
            "Le PDF de référence ne peut pas être exporté comme version comparée.",
            status_code=400,
        )
    item = next(
        (entry for entry in report["comparisons"] if entry["document_index"] == document_index),
        None,
    )
    if item is None:
        raise AppError("COMPARISON_FILE_NOT_FOUND", "PDF comparé introuvable.", status_code=404)
    path = safe_storage_join(
        comparison_root(),
        comparison_id.hex,
        f"document-{document_index}.pdf",
    )
    if not path.is_file():
        raise AppError("COMPARISON_FILE_MISSING", "Le PDF enregistré est introuvable.", status_code=404)
    reference_filename = report["documents"][reference_index]["filename"]
    content = build_commented_pdf(
        path,
        reference_filename=reference_filename,
        comparison=item,
        language=language,
    )
    filename = safe_filename(f"{Path(item['filename']).stem}_diff.pdf")
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
    report = load_report(row)
    indices = [item["document_index"] for item in report["comparisons"]]
    if len(indices) == 1:
        content, filename = _commented_pdf(
            row.id, row.reference_index, report, indices[0], language
        )
        return _pdf_response(content, filename)

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for document_index in indices:
            content, filename = _commented_pdf(
                row.id, row.reference_index, report, document_index, language
            )
            zipped.writestr(f"{document_index + 1:02d}_{filename}", content)
    return Response(
        content=archive.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="comparisons_diff.zip"'},
    )


@router.get("/{comparison_id}/export/{document_index}")
def export_comparison_document(
    comparison_id: uuid.UUID,
    document_index: int,
    language: Literal["fr", "en"] = Query("fr"),
    db: Session = Depends(get_db),
) -> Response:
    row = get_comparison(comparison_id, db)
    report = load_report(row)
    content, filename = _commented_pdf(
        row.id, row.reference_index, report, document_index, language
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
