"""Routes de detection, apercu et validation de la plage PDF a analyser."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api_models import PdfCutConfirmedOut, PdfCutDetectionOut
from app.config import settings
from app.core import pdf_cut
from app.core.errors import AppError
from app.db.models import Document
from app.db.session import get_db
from app.schemas import PdfCutConfirmIn, PdfCutDetectIn

router = APIRouter(prefix="/documents", tags=["pdf-cut"])


def _require(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
    return doc


@router.post("/{doc_id}/pdf-cut/detect", response_model=PdfCutDetectionOut)
def detect_pdf_start(
    doc_id: str,
    params: PdfCutDetectIn = Body(default=PdfCutDetectIn()),
    db: Session = Depends(get_db),
) -> dict:
    doc = _require(db, doc_id)
    candidates = pdf_cut.detect_start_pages(doc, params.title)
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
def preview_pdf_page(doc_id: str, page_number: int, db: Session = Depends(get_db)) -> FileResponse:
    doc = _require(db, doc_id)
    return FileResponse(pdf_cut.preview_path(doc, page_number), media_type="image/png",
                        headers={"Cache-Control": "private, max-age=3600"})


@router.post("/{doc_id}/pdf-cut/confirm", response_model=PdfCutConfirmedOut)
def confirm_pdf_start(
    doc_id: str,
    params: PdfCutConfirmIn,
    db: Session = Depends(get_db),
) -> dict:
    doc = _require(db, doc_id)
    pdf_cut.cut_from_page(doc, params.start_page, params.end_page)
    db.commit()
    return {
        "page": params.start_page,
        "start_page": params.start_page,
        "end_page": doc.pdf_cut_end_page,
        "page_count": doc.page_count,
        "status": "ready",
    }
