from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.checks.client_registry import LoadedClientConfiguration
from app.checks.mode_registry import get_request_client_configuration
from app.core.demo_scope import get_document_in_current_mode
from app.core.errors import AppError
from app.db.models import Document


def get_preparation_context(
    request: Request,
    document_id: uuid.UUID,
    db: Session,
) -> tuple[Document, LoadedClientConfiguration]:
    document = get_document_in_current_mode(db, document_id)
    if document is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable.", status_code=404)
    if document.working_format != "pdf":
        raise AppError(
            "PREPARATION_FORMAT_UNSUPPORTED",
            "La préparation est disponible uniquement pour les CMM PDF.",
            status_code=422,
        )
    client_configuration = get_request_client_configuration(request, db)
    if client_configuration.manifest.client_code != "THALES":
        raise AppError(
            "PREPARATION_CLIENT_UNSUPPORTED",
            "La préparation par checklist est actuellement réservée au bundle THALES.",
            status_code=422,
        )
    return document, client_configuration
