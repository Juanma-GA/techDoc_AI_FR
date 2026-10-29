from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.checks.client_registry import LoadedClientConfiguration
from app.checks.thales_rules.section_detection import page_types_for_titles
from app.checks.thales_rules.preparation_detector import detect_pages_to_modify
from app.core.compiled_rules import CompiledRule
from app.core.errors import AppError
from app.core.pdf_versioning import current_path
from app.core.preparation_classification import (
    load_page_classification,
    load_preparation_page_titles,
)
from app.core.preparation_state import (
    _load_json,
    _load_validation_map,
    get_or_create_record,
    load_preparation_mapping,
)
from app.db.models import Document
from app.db.preparation_models import DocumentPreparation, PreparationChecklist
from app.parsers.pdf_parser import ParsedPdf, PdfLine, Span, parse_pdf


def apply_preparation_ocr(parsed: ParsedPdf, record: DocumentPreparation) -> None:
    page_metadata = _load_json(record.page_metadata_json, "page_metadata_json")
    if not isinstance(page_metadata, list) or any(
        not isinstance(item, dict) or type(item.get("page")) is not int
        for item in page_metadata
    ):
        raise AppError(
            "PREPARATION_STATE_INVALID",
            "L'état de préparation (page_metadata_json) est illisible.",
            status_code=500,
        )
    if record.selected_provider != "mistral":
        raise AppError(
            "OCR_PROVIDER_NOT_SELECTED",
            "Mistral OCR doit être exécuté sur tout le document avant l'analyse.",
            status_code=409,
        )
    required_pages = [page["page"] for page in page_metadata if page.get("needs_ocr")]
    validated_by_provider = _load_validation_map(record)
    validated = set(validated_by_provider.get("mistral", []))
    missing_pages = [page for page in required_pages if page not in validated]
    if missing_pages:
        raise AppError(
            "OCR_VALIDATION_REQUIRED",
            "Validez les résultats Mistral OCR de toutes les pages avant l'analyse de préparation.",
            status_code=409,
            detail={"pages": missing_pages},
        )
    ocr_results = _load_json(record.ocr_results_json, "ocr_results_json")
    mistral_results = ocr_results.get("mistral", {}) if isinstance(ocr_results, dict) else None
    if not isinstance(mistral_results, dict):
        raise AppError(
            "PREPARATION_STATE_INVALID",
            "L'état de préparation (ocr_results_json) est illisible.",
            status_code=500,
        )
    _apply_ocr_text(parsed, page_metadata, mistral_results)


def detect_preparation_pages(
    db: Session,
    document: Document,
    client_configuration: LoadedClientConfiguration,
    *,
    preserve_manual: bool = False,
) -> list[dict]:
    record = get_or_create_record(db, document)
    previous_decisions = _load_json(record.page_decisions_json, "page_decisions_json")
    rules = [
        definition.compiled_rule
        for definition in client_configuration.bundle.rules
        if definition.preparation
    ]
    checklist = db.get(PreparationChecklist, client_configuration.bundle.client_code)
    if checklist is not None:
        rules.extend(
            CompiledRule.model_validate(item)
            for item in _load_json(checklist.rules_json, "rules_json")
        )
    if not rules:
        raise AppError(
            "PREPARATION_CHECKLIST_MISSING",
            "Aucune règle de préparation n'est configurée.",
            status_code=409,
        )
    parsed = parse_pdf(current_path(document.storage_dir, document.current_version))
    apply_preparation_ocr(parsed, record)
    metadata = preparation_metadata(
        client_configuration.bundle.mapping.fields,
        load_preparation_mapping(record),
    )
    decisions = detect_pages_to_modify(
        parsed,
        PreparationDocument(document, metadata),
        rules,
        db,
        client_configuration.bundle,
        load_page_classification(record),
        metadata,
        page_types_for_titles(
            load_preparation_page_titles(db, client_configuration.bundle.client_code)
        )
        if client_configuration.bundle.client_code == "THALES"
        else None,
    )
    if preserve_manual:
        _carry_over_manual_decisions(decisions, previous_decisions)
    record.page_decisions_json = json.dumps(decisions, ensure_ascii=False)
    record.updated_at = datetime.now(UTC)
    db.commit()
    return decisions


_METADATA_FIELDS = (
    "meta_revision_date",
    "meta_cmm_number",
    "meta_first_issue_date",
    "meta_last_issue_date",
    "meta_revision_number",
    "meta_pnr_number",
    "meta_manufacturer",
    "document_language",
)


def preparation_metadata(
    fields: Mapping[str, Any],
    saved_mapping: Mapping[str, Any],
) -> dict[str, Any]:
    """The preparation mapping completed with field defaults, as the analysis does."""
    metadata = {name: saved_mapping[name] for name in fields if name in saved_mapping}
    for name, definition in fields.items():
        metadata.setdefault(name, definition.default)
    return metadata


class PreparationDocument:
    """Document view whose metadata comes only from the preparation mapping."""

    def __init__(self, document: Document, metadata: Mapping[str, Any]) -> None:
        self._document = document
        self.client_metadata = dict(metadata)
        for name in _METADATA_FIELDS:
            setattr(self, name, metadata.get(name))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._document, name)


def _carry_over_manual_decisions(
    decisions: list[dict[str, Any]],
    previous: list[dict[str, Any]],
) -> None:
    """Keep a manual modified/unchanged choice while the page type is unchanged."""
    previous_by_page = {item.get("page"): item for item in previous}
    for decision in decisions:
        old = previous_by_page.get(decision["page"])
        if (
            old is not None
            and old.get("manual_override")
            and old.get("is_modified") is not None
            and old.get("page_type") == decision["page_type"]
        ):
            decision["is_modified"] = old["is_modified"]
            decision["decision_status"] = "selected" if old["is_modified"] else "not_selected"
            decision["manual_override"] = True


def _apply_ocr_text(
    parsed: ParsedPdf,
    page_metadata: list[dict[str, Any]],
    results: dict[str, Any],
) -> None:
    metadata_by_page = {int(item["page"]): item for item in page_metadata}
    for page in parsed.pages:
        metadata = metadata_by_page.get(page.page)
        if metadata is None or not metadata.get("needs_ocr"):
            continue
        result = results.get(str(page.page))
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise AppError(
                "OCR_RESULT_MISSING",
                f"Le résultat OCR de la page {page.page} est indisponible.",
                status_code=409,
            )
        page.text = result["text"]
        page.has_text_layer = False
        spans: list[Span] = []
        lines: list[PdfLine] = []
        for index, box in enumerate(result.get("boxes", [])):
            if not isinstance(box, dict):
                continue
            coordinates = [box.get(key) for key in ("x0", "y0", "x1", "y1")]
            text = box.get("text")
            if (
                not isinstance(text, str)
                or not text.strip()
                or any(
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    for value in coordinates
                )
                or page.page_width <= 0
                or page.page_height <= 0
            ):
                continue
            x0, y0, x1, y1 = (float(value) for value in coordinates)
            if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                continue
            bbox = (
                x0 * page.page_width,
                y0 * page.page_height,
                x1 * page.page_width,
                y1 * page.page_height,
            )
            spans.append(Span(text=text, bbox=bbox, page=page.page, font="", size=0.0))
            lines.append(
                PdfLine(
                    text=text,
                    bbox=bbox,
                    block_index=index,
                    line_index=0,
                )
            )
        page.spans = spans
        page.lines = lines
    parsed.full_text = "\n".join(
        f"[PAGE: {page.page}]\n{page.text}" for page in parsed.pages
    )
