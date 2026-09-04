"""Routes de detection, apercu et validation du debut de chapitre PDF."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import settings
from app.core import pdf_cut
from app.core.errors import AppError
from app.db.models import Document
from app.db.session import get_db

router = APIRouter(prefix="/documents", tags=["pdf-cut"])


def _require(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
    return doc


@router.post("/{doc_id}/pdf-cut/detect")
def detect_pdf_start(doc_id: str, db: Session = Depends(get_db)) -> dict:
    doc = _require(db, doc_id)
    candidates = pdf_cut.detect_start_pages(doc)
    return {
        "validation_required": settings.pdf_cut_requires_validation,
        "selected_page": doc.pdf_cut_start_page,
        "candidates": candidates[:10],
    }


@router.get("/{doc_id}/pdf-cut/preview/{page_number}")
def preview_pdf_page(doc_id: str, page_number: int, db: Session = Depends(get_db)) -> Response:
    doc = _require(db, doc_id)
    return Response(content=pdf_cut.preview_page(doc, page_number), media_type="image/png")


@router.post("/{doc_id}/pdf-cut/confirm")
def confirm_pdf_start(
    doc_id: str,
    params: dict = Body(default={}),
    db: Session = Depends(get_db),
) -> dict:
    doc = _require(db, doc_id)
    page_number = params.get("page")
    if isinstance(page_number, bool) or not isinstance(page_number, int):
        raise AppError("PDF_PAGE_INVALID", "Le champ page doit etre un entier.", 422)
    pdf_cut.cut_from_page(doc, page_number)
    db.commit()
    return {
        "page": page_number,
        "page_count": doc.page_count,
        "status": "ready",
    }
