"""Read-only metadata suggestions for an imported PDF."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.checks.mode_registry import get_request_client_configuration
from app.core.demo_scope import get_document_in_current_mode
from app.core.errors import AppError
from app.core.norm_detection import detect_document_norm, read_page_texts
from app.core.pdf_versioning import current_path
from app.core.preparation_state import get_record, get_validated_ocr_page_text
from app.db.session import get_db
from app.parsers.cmm_metadata import (
    MAX_METADATA_PAGES,
    suggest_cmm_metadata_from_pages,
)

router = APIRouter(tags=["documents"])

# Front matter read to recognise a norm and to find its update reasons (HIGHLIGHTS follow the LOEDM).
NORM_SCAN_PAGES = 20


class DocumentMetadataSuggestionsOut(BaseModel):
    pages_scanned: int = Field(ge=0, le=NORM_SCAN_PAGES)
    meta_cmm_number: str | None = None
    meta_pnr_number: list[str] = Field(default_factory=list, max_length=50)
    meta_revision_number: str | None = None
    meta_revision_date: str | None = None
    meta_first_issue_date: str | None = None
    meta_update_type: str | None = None


@router.post(
    "/documents/{document_id}/metadata-suggestions",
    response_model=DocumentMetadataSuggestionsOut,
    # `meta_update_type` is only suggested by norms that have one (S1000D).
    response_model_exclude_unset=True,
)
def suggest_document_metadata(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> DocumentMetadataSuggestionsOut:
    document = get_document_in_current_mode(db, document_id)
    if document is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    if document.working_format != "pdf":
        raise AppError(
            "METADATA_SUGGESTIONS_UNAVAILABLE",
            "La détection du mapping est disponible uniquement pour les PDF.",
            status_code=409,
        )

    pdf_path = current_path(document.storage_dir, document.current_version)
    if not pdf_path.is_file():
        raise AppError("PDF_VERSION_MISSING", "Snapshot absent", status_code=404)
    try:
        page_texts = read_page_texts(pdf_path, NORM_SCAN_PAGES)
        record = get_record(db, document.id)
        if (
            record is not None
            and record.source_version == document.current_version
            and record.selected_provider == "mistral"
        ):
            for page_number in range(1, min(MAX_METADATA_PAGES, document.page_count) + 1):
                text = get_validated_ocr_page_text(record, "mistral", page_number)
                if text is not None and text.strip() and page_number <= len(page_texts):
                    page_texts[page_number - 1] = text
        bundle = get_request_client_configuration(request, db).bundle
        norm = detect_document_norm(bundle, page_texts)
        suggester = bundle.norm_metadata_suggesters.get(norm) if norm else None
        if suggester is not None:
            return DocumentMetadataSuggestionsOut(
                pages_scanned=len(page_texts), **suggester(page_texts)
            )
        return DocumentMetadataSuggestionsOut(**suggest_cmm_metadata_from_pages(page_texts))
    except (OSError, RuntimeError, ValueError) as exc:
        raise AppError("PDF_INVALID", "PDF illisible", status_code=400) from exc
