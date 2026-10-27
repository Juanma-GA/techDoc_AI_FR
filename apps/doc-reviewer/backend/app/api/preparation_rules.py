from __future__ import annotations

import json
import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.api.preparation_common import get_preparation_context
from app.checks.thales_rules.preparation_checklist import (
    checksum,
    compile_preparation_checklist,
)
from app.config import settings
from app.core.errors import AppError
from app.core.preparation_annotations import sync_toc_annotations
from app.core.preparation_check_service import detect_preparation_pages
from app.core.preparation_classification import (
    available_page_types,
    set_absent_page_types,
    set_page_classification,
)
from app.core.preparation_state import get_or_create_record, set_page_decision
from app.core.security import read_upload_limited, safe_filename
from app.db.preparation_models import PreparationChecklist
from app.db.session import get_db
from app.preparation_schemas import (
    AbsentPageTypesPatchIn,
    ChecklistImportOut,
    PageClassificationPatchIn,
    PageDecisionPatchIn,
)

router = APIRouter(tags=["preparation"])


@router.get("/preparation/checklist/template")
def download_checklist_template() -> StreamingResponse:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "THALES preparation"
    sheet.append(["code", "name", "page_type", "zone", "check", "severity", "comment"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="thales-preparation-checklist.xlsx"'},
    )


@router.post(
    "/documents/{document_id}/preparation/checklist",
    response_model=ChecklistImportOut,
)
def import_preparation_checklist(
    document_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    _document, client_configuration = get_preparation_context(request, document_id, db)
    filename = safe_filename(file.filename)
    if not filename.lower().endswith((".xlsx", ".xlsm")):
        raise AppError(
            "PREPARATION_CHECKLIST_BAD_FORMAT",
            "La checklist de préparation doit être au format .xlsx ou .xlsm.",
            status_code=400,
        )
    data = read_upload_limited(file, settings.max_upload_size_bytes)
    rules = compile_preparation_checklist(
        data,
        filename,
        db,
        client_configuration.bundle,
    )
    client_code = client_configuration.bundle.client_code
    serialized_rules = json.dumps(
        [rule.model_dump(mode="json", exclude_none=False) for rule in rules],
        ensure_ascii=False,
    )
    row = db.get(PreparationChecklist, client_code)
    if row is None:
        row = PreparationChecklist(
            client_code=client_code,
            source_filename=filename,
            rules_json=serialized_rules,
            content_sha256=checksum(data),
        )
        db.add(row)
    else:
        row.source_filename = filename
        row.rules_json = serialized_rules
        row.content_sha256 = checksum(data)
    db.commit()
    return {
        "client_code": client_code,
        "source_filename": filename,
        "imported": len(rules),
        "unsupported": sum(rule.execution == "unsupported" for rule in rules),
        "content_sha256": row.content_sha256,
    }


@router.post("/documents/{document_id}/preparation/detect")
def detect_pages(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> list[dict]:
    document, client_configuration = get_preparation_context(request, document_id, db)
    return detect_preparation_pages(db, document, client_configuration)


@router.patch("/documents/{document_id}/preparation/decisions/{page_number}")
def patch_decision(
    document_id: uuid.UUID,
    page_number: int,
    body: PageDecisionPatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, _config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    decisions = set_page_decision(db, record, page_number, body.is_modified)
    return {"decisions": decisions}


@router.patch("/documents/{document_id}/preparation/pages/{page_number}/classification")
def patch_page_classification(
    document_id: uuid.UUID,
    page_number: int,
    body: PageClassificationPatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, client_configuration = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    classification = set_page_classification(
        db,
        record,
        page_number,
        body.page_type,
        body.document_page,
        available_page_types(db, client_configuration.bundle),
    )
    has_decisions = record.page_decisions_json != "[]"
    decisions = (
        detect_preparation_pages(db, document, client_configuration, preserve_manual=True)
        if has_decisions
        else []
    )
    return {"page": page_number, "classification": classification, "decisions": decisions}


@router.patch("/documents/{document_id}/preparation/absent-page-types")
def patch_absent_page_types(
    document_id: uuid.UUID,
    body: AbsentPageTypesPatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, client_configuration = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    absent = set_absent_page_types(
        db,
        record,
        body.page_types,
        body.absent,
        available_page_types(db, client_configuration.bundle),
    )
    return {"absent_page_types": absent}


@router.post("/documents/{document_id}/preparation/toc-annotations")
def create_toc_annotations(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    document, _config = get_preparation_context(request, document_id, db)
    record = get_or_create_record(db, document)
    return {"created": sync_toc_annotations(db, document, record)}
