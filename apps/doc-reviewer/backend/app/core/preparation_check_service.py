from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.checks.client_registry import LoadedClientConfiguration
from app.checks.thales_rules.preparation_detector import detect_pages_to_modify
from app.core.compiled_rules import CompiledRule
from app.core.errors import AppError
from app.core.pdf_versioning import current_path
from app.core.preparation_state import _load_json, _load_validation_map, get_or_create_record
from app.db.models import Document
from app.db.preparation_models import PreparationChecklist
from app.parsers.pdf_parser import parse_pdf


def detect_preparation_pages(
    db: Session,
    document: Document,
    client_configuration: LoadedClientConfiguration,
) -> list[dict]:
    record = get_or_create_record(db, document)
    page_metadata = _load_json(record.page_metadata_json, "page_metadata_json")
    unreadable = [page["page"] for page in page_metadata if page["needs_ocr"]]
    if unreadable:
        if not record.selected_provider:
            raise AppError(
                "OCR_PROVIDER_NOT_SELECTED",
                "Choisissez un moteur OCR.",
                status_code=409,
            )
        validated_by_provider = _load_validation_map(record)
        validated = set(
            validated_by_provider.get(
                record.selected_provider,
                [],
            )
        )
        if any(page not in validated for page in unreadable):
            raise AppError(
                "OCR_VALIDATION_REQUIRED",
                "Validez le résultat OCR de chaque page marquée illisible avant la checklist.",
                status_code=409,
                detail={"pages": [page for page in unreadable if page not in validated]},
            )
    checklist = db.get(PreparationChecklist, client_configuration.bundle.client_code)
    if checklist is None:
        raise AppError(
            "PREPARATION_CHECKLIST_MISSING",
            "Importez d'abord la checklist de préparation THALES.",
            status_code=409,
        )
    rules = [
        CompiledRule.model_validate(item)
        for item in _load_json(checklist.rules_json, "rules_json")
    ]
    parsed = parse_pdf(current_path(document.storage_dir, document.current_version))
    decisions = detect_pages_to_modify(
        parsed,
        document,
        rules,
        db,
        client_configuration.bundle,
    )
    record.page_decisions_json = json.dumps(decisions, ensure_ascii=False)
    record.updated_at = datetime.now(UTC)
    db.commit()
    return decisions
