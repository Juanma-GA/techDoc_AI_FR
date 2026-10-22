"""Routes de detection, apercu et validation de la plage PDF a analyser."""

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
def detect_pdf_start(
    doc_id: str,
    params: dict = Body(default={}),
    db: Session = Depends(get_db),
) -> dict:
    doc = _require(db, doc_id)
    title = params.get("title")
    if title is not None and not isinstance(title, str):
        raise AppError("PDF_DM_TITLE_INVALID", "Le titre selectionne doit etre du texte.", 422)
    candidates = pdf_cut.detect_start_pages(doc, title)
    total_pages = pdf_cut.total_pages(doc)
    return {
        "validation_required": settings.pdf_cut_requires_validation,
        "selected_page": doc.pdf_cut_start_page,
        "selected_end_page": doc.pdf_cut_end_page,
        "default_start_page": candidates[0]["page"] if candidates else 1,
        "total_pages": total_pages,
        "dmrl_titles": pdf_cut.dmrl_data_module_titles(doc.dmrl_json),
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
    start_page = params.get("start_page", params.get("page"))
    end_page = params.get("end_page")
    if isinstance(start_page, bool) or not isinstance(start_page, int):
        raise AppError("PDF_PAGE_INVALID", "Le champ start_page doit etre un entier.", 422)
    if end_page is not None and (isinstance(end_page, bool) or not isinstance(end_page, int)):
        raise AppError("PDF_PAGE_INVALID", "Le champ end_page doit etre un entier.", 422)
    pdf_cut.cut_from_page(doc, start_page, end_page)
    db.commit()
    return {
        "page": start_page,
        "start_page": start_page,
        "end_page": doc.pdf_cut_end_page,
        "page_count": doc.page_count,
        "status": "ready",
    }
