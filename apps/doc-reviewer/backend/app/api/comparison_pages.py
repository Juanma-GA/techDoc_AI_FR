"""Render a saved comparison PDF page to PNG for the side-by-side viewer."""

from __future__ import annotations

import uuid

import fitz
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.comparison_report import ensure_current_report
from app.core.errors import AppError
from app.core.security import safe_storage_join
from app.db.session import get_db

from .comparisons import comparison_root, get_comparison

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


@router.get("/{comparison_id}/documents/{document_index}/pages/{page_number}.png")
def render_comparison_page(
    comparison_id: uuid.UUID,
    document_index: int,
    page_number: int,
    dpi: int = Query(default=120, ge=72, le=300),
    db: Session = Depends(get_db),
) -> Response:
    row = get_comparison(comparison_id, db)
    report = ensure_current_report(row, db)
    documents = report["documents"]
    if document_index < 0 or document_index >= len(documents):
        raise AppError("COMPARISON_FILE_NOT_FOUND", "PDF introuvable.", status_code=404)

    page_count = int(documents[document_index]["page_count"])
    if page_number < 1 or page_number > page_count:
        raise AppError(
            "COMPARISON_PAGE_NOT_FOUND",
            f"Page {page_number} absente de ce PDF.",
            status_code=404,
        )

    path = safe_storage_join(
        comparison_root(),
        row.id.hex,
        f"document-{document_index}.pdf",
    )
    if not path.is_file():
        raise AppError("COMPARISON_FILE_MISSING", "Le PDF enregistré est introuvable.", status_code=404)
    try:
        document = fitz.open(str(path))
    except (fitz.FileDataError, RuntimeError) as exc:
        raise AppError("PDF_INVALID", "Le PDF enregistré est illisible.", status_code=500) from exc
    try:
        page = document.load_page(page_number - 1)
        png_bytes = page.get_pixmap(dpi=dpi, alpha=False).tobytes("png")
    finally:
        document.close()

    etag = f'"{row.id.hex}:{document_index}:{page_number}:{dpi}"'
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=60", "ETag": etag},
    )
