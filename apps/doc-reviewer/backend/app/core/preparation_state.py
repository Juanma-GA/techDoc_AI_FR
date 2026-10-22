from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.pdf_versioning import current_path
from app.core.preparation_readability import (
    READABILITY_VERSION,
    analyze_pdf_pages,
)
from app.db.models import Document
from app.db.preparation_models import DocumentPreparation, PreparationChecklist


def get_record(db: Session, document_id: uuid.UUID) -> DocumentPreparation | None:
    return db.scalar(
        select(DocumentPreparation).where(DocumentPreparation.document_id == document_id)
    )


def get_or_create_record(db: Session, document: Document) -> DocumentPreparation:
    record = get_record(db, document.id)
    if record is not None and record.source_version == document.current_version:
        pages = _load_json(record.page_metadata_json, "page_metadata_json")
        readability_changed = (
            len(pages) != record.page_count
            or any(page.get("readability_version") != READABILITY_VERSION for page in pages)
        )
        if readability_changed:
            try:
                page_metadata = analyze_pdf_pages(
                    current_path(document.storage_dir, document.current_version).read_bytes()
                )
            except OSError as exc:
                raise AppError(
                    "PREPARATION_DOCUMENT_INVALID",
                    "Le document PDF ne peut pas être lu pour la préparation.",
                    status_code=400,
                ) from exc
            record.page_metadata_json = json.dumps(page_metadata)
            record.page_decisions_json = "[]"
        provider_changed = record.selected_provider != "mistral"
        if provider_changed:
            record.ocr_results_json = "{}"
            record.validated_pages_json = "{}"
            record.page_decisions_json = "[]"
            record.selected_provider = "mistral"
        if readability_changed or provider_changed:
            record.updated_at = datetime.now(UTC)
            db.commit()
        return record

    path = current_path(document.storage_dir, document.current_version)
    try:
        data = path.read_bytes()
        page_metadata = analyze_pdf_pages(data)
    except OSError as exc:
        raise AppError(
            "PREPARATION_DOCUMENT_INVALID",
            "Le document PDF ne peut pas être lu pour la préparation.",
            status_code=400,
        ) from exc
    page_count = len(page_metadata)

    if record is None:
        record = DocumentPreparation(
            document_id=document.id,
            source_filename=document.original_filename,
            source_sha256=sha256(data).hexdigest(),
            page_count=page_count,
            source_version=document.current_version,
            selected_provider="mistral",
            page_metadata_json=json.dumps(page_metadata),
        )
        db.add(record)
    else:
        record.source_filename = document.original_filename
        record.source_sha256 = sha256(data).hexdigest()
        record.page_count = page_count
        record.source_version = document.current_version
        record.page_metadata_json = json.dumps(page_metadata)
        record.ocr_results_json = "{}"
        record.validated_pages_json = "{}"
        record.selected_provider = None
        record.page_decisions_json = "[]"
        record.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(record)
    return record


def state_payload(
    db: Session,
    document: Document,
    client_code: str,
    *,
    preparation_rule_count: int = 0,
) -> dict[str, Any]:
    record = get_record(db, document.id)
    checklist = db.get(PreparationChecklist, client_code)
    if record is None:
        pages = []
        filename = source_sha256 = provider = None
        preparation_mapping = {}
        page_count = 0
        validated: list[int] = []
        available_results: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
    else:
        pages = _load_json(record.page_metadata_json, "page_metadata_json")
        filename = record.source_filename
        source_sha256 = record.source_sha256
        provider = record.selected_provider
        preparation_mapping = load_preparation_mapping(record)
        page_count = record.page_count
        validated_by_provider = _load_validation_map(record)
        validated = validated_by_provider.get(provider, []) if provider else []
        ocr_results = _load_json(record.ocr_results_json, "ocr_results_json")
        available_results = [
            {"provider": provider_name, "page": int(page_number)}
            for provider_name, provider_results in ocr_results.items()
            for page_number in provider_results
        ]
        decisions = _load_json(record.page_decisions_json, "page_decisions_json")
    rules = _load_json(checklist.rules_json, "rules_json") if checklist else []
    return {
        "document_id": str(document.id),
        "source_filename": filename,
        "source_sha256": source_sha256,
        "page_count": page_count,
        "selected_provider": provider,
        "pages": pages,
        "ocr_results_available": available_results,
        "validated_pages": validated,
        "checklist_rule_count": preparation_rule_count + len(rules),
        "checklist_imported_rule_count": len(rules),
        "preparation_rule_count": preparation_rule_count,
        "checklist_source_filename": checklist.source_filename if checklist else None,
        "page_decisions": decisions,
        "preparation_mapping": preparation_mapping,
    }


def load_preparation_mapping(record: DocumentPreparation) -> dict[str, Any]:
    mapping = _load_json(record.preparation_mapping_json, "preparation_mapping_json")
    if not isinstance(mapping, dict):
        raise AppError(
            "PREPARATION_MAPPING_INVALID",
            "Le mapping de préparation enregistré est invalide.",
            status_code=500,
        )
    return mapping


def update_preparation_mapping(
    db: Session,
    record: DocumentPreparation,
    mapping: dict[str, Any],
) -> None:
    record.preparation_mapping_json = json.dumps(mapping, ensure_ascii=False)
    record.updated_at = datetime.now(UTC)
    db.commit()


def update_readability(
    db: Session,
    record: DocumentPreparation,
    page_number: int,
    needs_ocr: bool,
) -> None:
    pages = _load_json(record.page_metadata_json, "page_metadata_json")
    page = _find_page(pages, page_number)
    page["needs_ocr"] = needs_ocr
    record.page_metadata_json = json.dumps(pages)
    record.updated_at = datetime.now(UTC)
    db.commit()


def select_provider(db: Session, record: DocumentPreparation, provider: str) -> None:
    record.selected_provider = provider
    record.updated_at = datetime.now(UTC)
    db.commit()


def set_ocr_validation(
    db: Session,
    record: DocumentPreparation,
    page_number: int,
    provider: str,
    validated: bool,
) -> None:
    if validated and get_page_ocr_result(record, provider, page_number) is None:
        raise AppError(
            "OCR_RESULT_MISSING",
            "Lancez l'OCR de cette page avant de valider son résultat.",
            status_code=409,
        )
    validated_by_provider = _load_validation_map(record)
    pages = set(validated_by_provider.get(provider, []))
    if validated:
        pages.add(page_number)
    else:
        pages.discard(page_number)
    validated_by_provider[provider] = sorted(pages)
    record.validated_pages_json = json.dumps(validated_by_provider)
    record.updated_at = datetime.now(UTC)
    db.commit()


def validate_all_ocr_pages(
    db: Session,
    record: DocumentPreparation,
) -> list[int]:
    page_metadata = _load_json(record.page_metadata_json, "page_metadata_json")
    ocr_results = _load_json(record.ocr_results_json, "ocr_results_json")
    mistral_results = ocr_results.get("mistral", {})
    pages = [int(page["page"]) for page in page_metadata if page.get("needs_ocr")]
    missing = [page for page in pages if str(page) not in mistral_results]
    if missing:
        raise AppError(
            "OCR_RESULTS_INCOMPLETE",
            "Lancez Mistral OCR sur toutes les pages qui en ont besoin avant de valider.",
            status_code=409,
            detail={"pages": missing},
        )
    record.selected_provider = "mistral"
    record.validated_pages_json = json.dumps({"mistral": pages})
    record.updated_at = datetime.now(UTC)
    db.commit()
    return pages


def set_page_decision(
    db: Session,
    record: DocumentPreparation,
    page_number: int,
    is_modified: bool,
) -> list[dict[str, Any]]:
    decisions = _load_json(record.page_decisions_json, "page_decisions_json")
    decision = next((item for item in decisions if item.get("page") == page_number), None)
    if decision is None:
        raise AppError(
            "PAGE_DECISION_NOT_FOUND",
            "Cette page n'a pas de décision à corriger.",
            status_code=404,
        )
    decision["is_modified"] = is_modified
    decision["decision_status"] = "selected" if is_modified else "not_selected"
    decision["manual_override"] = True
    record.page_decisions_json = json.dumps(decisions, ensure_ascii=False)
    record.updated_at = datetime.now(UTC)
    db.commit()
    return decisions


def get_page_ocr_result(
    record: DocumentPreparation,
    provider: str,
    page_number: int,
) -> dict[str, Any] | None:
    results = _load_json(record.ocr_results_json, "ocr_results_json")
    return results.get(provider, {}).get(str(page_number))


def _find_page(pages: list[dict[str, Any]], page_number: int) -> dict[str, Any]:
    page = next((item for item in pages if item.get("page") == page_number), None)
    if page is None:
        raise AppError("PAGE_RANGE_INVALID", "Numéro de page invalide.", status_code=422)
    return page


def _load_json(raw: str, field: str) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise AppError(
            "PREPARATION_STATE_INVALID",
            f"L'état de préparation ({field}) est illisible.",
            status_code=500,
        ) from exc


def _load_validation_map(record: DocumentPreparation) -> dict[str, list[int]]:
    value = _load_json(record.validated_pages_json, "validated_pages_json")
    if isinstance(value, dict):
        return value
    if value == []:
        return {}
    raise AppError(
        "PREPARATION_STATE_INVALID",
        "L'état de préparation (validated_pages_json) est illisible.",
        status_code=500,
    )
