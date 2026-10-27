from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.preparation_common import get_preparation_context
from app.core.client_metadata import validate_client_metadata_patch
from app.core.errors import AppError
from app.core.ocr_providers import available_providers
from app.core.preparation_classification import available_page_types, page_requirements
from app.core.preparation_state import (
    get_or_create_record,
    select_provider,
    state_payload,
    update_preparation_mapping,
    update_readability,
)
from app.db.session import get_db
from app.preparation_schemas import (
    PreparationMappingPatchIn,
    PreparationStateOut,
    ProviderPatchIn,
    ReadabilityPatchIn,
)

router = APIRouter(tags=["preparation"])


@router.patch("/documents/{document_id}/preparation/mapping")
def patch_preparation_mapping(
    document_id: uuid.UUID,
    body: PreparationMappingPatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, config = get_preparation_context(request, document_id, db)
    validate_client_metadata_patch(body.mapping, config.mapping.fields)
    record = get_or_create_record(db, document)
    update_preparation_mapping(db, record, body.mapping)
    return {"preparation_mapping": body.mapping}


@router.get("/documents/{document_id}/preparation", response_model=PreparationStateOut)
def get_preparation_state(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    preparation_rule_count = sum(rule.preparation for rule in config.bundle.rules)
    payload = state_payload(
        db,
        document,
        config.bundle.client_code,
        preparation_rule_count=preparation_rule_count,
        page_type_options=available_page_types(db, config.bundle),
    )
    payload.update(page_requirements(db, config.bundle, record, payload["page_decisions"]))
    return payload


@router.get("/documents/{document_id}/preparation/ocr/providers")
def get_ocr_providers(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> list[dict]:
    get_preparation_context(request, document_id, db)
    return available_providers()


@router.patch("/documents/{document_id}/preparation/provider")
def patch_selected_provider(
    document_id: uuid.UUID,
    body: ProviderPatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, _config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    available = {item["id"]: item for item in available_providers()}
    provider = available[body.provider]
    if not provider["available"]:
        raise AppError(
            provider["reason"] or "OCR_PROVIDER_UNAVAILABLE",
            f"{provider['label']} n'est pas disponible.",
            status_code=503,
        )
    select_provider(db, record, body.provider)
    return {"selected_provider": body.provider}


@router.patch("/documents/{document_id}/preparation/pages/{page_number}")
def patch_page_readability(
    document_id: uuid.UUID,
    page_number: int,
    body: ReadabilityPatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, _config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    update_readability(db, record, page_number, body.needs_ocr)
    return {"page": page_number, "needs_ocr": body.needs_ocr}
