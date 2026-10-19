"""Read-only metadata suggestions for an imported PDF."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.demo_scope import get_document_in_current_mode
from app.core.errors import AppError
from app.core.pdf_versioning import current_path
from app.db.session import get_db
from app.parsers.cmm_metadata import (
    MAX_METADATA_PAGES,
    suggest_cmm_metadata_from_pdf,
)

router = APIRouter(tags=["documents"])


class DocumentMetadataSuggestionsOut(BaseModel):
    pages_scanned: int = Field(ge=0, le=MAX_METADATA_PAGES)
    meta_cmm_number: str | None = None
    meta_pnr_number: list[str] = Field(default_factory=list, max_length=50)
    meta_revision_number: str | None = None
    meta_revision_date: str | None = None
    meta_first_issue_date: str | None = None


@router.post(
    "/documents/{document_id}/metadata-suggestions",
    response_model=DocumentMetadataSuggestionsOut,
)
def suggest_document_metadata(
    document_id: uuid.UUID,
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
        return DocumentMetadataSuggestionsOut(
            **suggest_cmm_metadata_from_pdf(pdf_path)
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise AppError("PDF_INVALID", "PDF illisible", status_code=400) from exc
