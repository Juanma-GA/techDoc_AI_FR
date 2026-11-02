"""Typed review actions and on-demand PDF source anchors."""

from pathlib import Path

import pymupdf as fitz
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api_models import PageAnchorsOut, PreliminaryStateOut, SourcePageOut
from app.core import preliminary_review as review
from app.core.errors import AppError
from app.db.models import Document
from app.db.session import get_db

router = APIRouter(prefix="/documents", tags=["preliminary-review"])


def _require(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
    return doc


@router.post("/{doc_id}/wizard/preliminary", response_model=PreliminaryStateOut, response_model_exclude_unset=True)
def update_review(
    doc_id: str, action: review.ReviewAction, db: Session = Depends(get_db),
) -> dict:
    return review.apply(db, _require(db, doc_id), action)


@router.get("/{doc_id}/wizard/preliminary/{dm_id}/page/{page_number}", response_model=PageAnchorsOut)
def source_anchors(
    doc_id: str, dm_id: str, page_number: int, db: Session = Depends(get_db),
) -> dict:
    doc = _require(db, doc_id)
    if doc.source_format != "pdf":
        raise AppError("PDF_REQUIRED", "Les ancrages PDF exigent une source PDF.", 422)
    current = review.view(doc)["reviews"].get(dm_id)
    if current is None:
        raise AppError("REVIEW_DM_NOT_FOUND", "Procedure inconnue.", 404)
    if current["status"] == "stale":
        raise AppError("REVIEW_STALE", "Les ancrages sont obsoletes. Recommencez la revue.", 409)
    pages = [p["page"] for p in current["passages"] if p["page"]]
    if not pages or not min(pages) <= page_number <= max(pages):
        raise AppError("REVIEW_PAGE_INVALID", "Page hors de la procedure.", 422)
    path = Path(doc.storage_path)
    if not path.is_file():
        raise AppError("DOCUMENT_NOT_FOUND", "PDF source introuvable.", 404)
    try:
        with fitz.open(str(path)) as source:
            if not 1 <= page_number <= source.page_count:
                raise AppError("REVIEW_PAGE_INVALID", "Page source introuvable.", 422)
            page = source[page_number - 1]
            anchors = {}
            for passage in current["passages"]:
                if passage["page"] != page_number:
                    continue
                queries = passage["source_text"].split(" | ")
                boxes = [box for query in queries if query.strip() for box in page.search_for(query.strip())]
                anchors[passage["id"]] = [
                    [box.x0 / page.rect.width, box.y0 / page.rect.height,
                     box.x1 / page.rect.width, box.y1 / page.rect.height]
                    for box in boxes
                ]
            return {"width": page.rect.width, "height": page.rect.height, "anchors": anchors}
    except (OSError, fitz.FileDataError) as exc:
        raise AppError("PDF_UNREADABLE", "Impossible de lire la page source.", 422) from exc


@router.get("/{doc_id}/wizard/preliminary/{dm_id}/pages", response_model=list[SourcePageOut])
def source_pages(doc_id: str, dm_id: str, db: Session = Depends(get_db)) -> list[dict]:
    doc = _require(db, doc_id)
    current = review.view(doc)["reviews"].get(dm_id)
    if current is None:
        raise AppError("REVIEW_DM_NOT_FOUND", "Procedure inconnue.", 404)
    if doc.source_format != "pdf":
        raise AppError("PDF_REQUIRED", "La pagination source exige un PDF.", 422)
    if current["status"] == "stale":
        raise AppError("REVIEW_STALE", "Les pages sont obsoletes. Recommencez la revue.", 409)
    pages = [p["page"] for p in current["passages"] if p["page"]]
    if not pages:
        return []
    path = Path(doc.storage_path)
    if not path.is_file():
        raise AppError("DOCUMENT_NOT_FOUND", "PDF source introuvable.", 404)
    try:
        with fitz.open(str(path)) as source:
            if max(pages) > source.page_count:
                raise AppError("REVIEW_PAGE_INVALID", "Page source introuvable.", 422)
            return [
                {"page": number, "width": source[number - 1].rect.width,
                 "height": source[number - 1].rect.height}
                for number in range(min(pages), max(pages) + 1)
            ]
    except (OSError, fitz.FileDataError) as exc:
        raise AppError("PDF_UNREADABLE", "Impossible de lire les pages source.", 422) from exc
