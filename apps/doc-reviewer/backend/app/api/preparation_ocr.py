from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.preparation_common import get_preparation_context
from app.core.errors import AppError
from app.core.preparation_ocr_service import (
    get_native_page_text,
    run_document_ocr,
    run_page_ocr,
)
from app.core.preparation_state import (
    get_or_create_record,
    get_page_ocr_result,
    set_ocr_validation,
    validate_all_ocr_pages,
)
from app.db.session import get_db
from app.preparation_schemas import (
    OcrDocumentRunOut,
    OcrDocumentValidationOut,
    OcrResultOut,
    OcrRunIn,
    OcrValidationPatchIn,
    PreparationPageTextOut,
)

router = APIRouter(tags=["preparation"])


@router.post(
    "/documents/{document_id}/preparation/ocr",
    response_model=OcrDocumentRunOut,
)
def run_ocr_for_document(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, _config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    return run_document_ocr(db, document, record)


@router.get(
    "/documents/{document_id}/preparation/text/pages/{page_number}",
    response_model=PreparationPageTextOut,
)
def get_native_text_for_page(
    document_id: uuid.UUID,
    page_number: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, _config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    return get_native_page_text(document, record, page_number)


@router.post(
    "/documents/{document_id}/preparation/ocr/validation",
    response_model=OcrDocumentValidationOut,
)
def validate_ocr_for_document(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, _config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    return {
        "provider": "mistral",
        "validated_pages": validate_all_ocr_pages(db, record),
    }


@router.post(
    "/documents/{document_id}/preparation/ocr/pages/{page_number}",
    response_model=OcrResultOut,
)
def run_ocr_for_page(
    document_id: uuid.UUID,
    page_number: int,
    body: OcrRunIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, _config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    return run_page_ocr(db, document, record, page_number, body.provider)


@router.get(
    "/documents/{document_id}/preparation/ocr/pages/{page_number}",
    response_model=OcrResultOut,
)
def get_ocr_for_page(
    document_id: uuid.UUID,
    page_number: int,
    request: Request,
    provider: Literal["mistral", "paddle", "indra"] = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    document, _config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    result = get_page_ocr_result(record, provider, page_number)
    if result is None:
        raise AppError("OCR_RESULT_NOT_FOUND", "Résultat OCR introuvable.", status_code=404)
    return result


@router.patch(
    "/documents/{document_id}/preparation/ocr/pages/{page_number}/validation",
)
def patch_ocr_validation(
    document_id: uuid.UUID,
    page_number: int,
    body: OcrValidationPatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, _config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    set_ocr_validation(db, record, page_number, body.provider, body.validated)
    return {"page": page_number, "provider": body.provider, "validated": body.validated}
