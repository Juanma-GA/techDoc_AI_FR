"""Runtime metadata required before a document analysis can start."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.checks.client_bundle import ClientMapping
from app.db.models import AppConfig


REQUIRED_DOCUMENT_CONTEXT_FIELDS = (
    "meta_revision_date",
    "meta_cmm_number",
    "meta_first_issue_date",
    "meta_revision_number",
    "meta_manufacturer",
    "document_language",
)
# `meta_last_issue_date` (date de la revision precedente) reste optionnel :
# une premiere revision n'en a pas.
DOCUMENT_CONTEXT_FIELDS = REQUIRED_DOCUMENT_CONTEXT_FIELDS + (
    "meta_pnr_number",
    "meta_last_issue_date",
)

_DOCUMENT_CONTEXT_DEFAULTS_KEY = "document.context_defaults"
DOCUMENT_MANUFACTURERS = ("Airbus", "Boeing")
DEFAULT_DOCUMENT_MANUFACTURER = "Airbus"


def missing_document_context(
    document: Any,
    mapping: ClientMapping | None = None,
) -> list[str]:
    """Return required document metadata fields that are empty at runtime."""
    fields = (
        [name for name, definition in mapping.fields.items() if definition.required]
        if mapping is not None
        else list(REQUIRED_DOCUMENT_CONTEXT_FIELDS)
    )
    metadata = getattr(document, "client_metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    missing: list[str] = []
    for field in fields:
        value = metadata[field] if field in metadata else getattr(document, field, None)
        if isinstance(value, list):
            present = any(str(item).strip() for item in value if item is not None)
        else:
            present = bool(str(value or "").strip())
        if not present:
            missing.append(field)
    return missing


def get_document_context_defaults(
    db: Session,
    mapping: ClientMapping | None = None,
) -> dict[str, Any]:
    """Return the context copied onto newly imported documents."""
    if mapping is None:
        defaults: dict[str, Any] = {
            field: (
                DEFAULT_DOCUMENT_MANUFACTURER
                if field == "meta_manufacturer"
                else None
            )
            for field in DOCUMENT_CONTEXT_FIELDS
        }
        allowed_fields = set(DOCUMENT_CONTEXT_FIELDS)
    else:
        defaults = {
            field: definition.default
            for field, definition in mapping.fields.items()
            if definition.default is not None
        }
        allowed_fields = set(mapping.fields)

    row = db.get(AppConfig, _DOCUMENT_CONTEXT_DEFAULTS_KEY)
    if row is None or not row.value:
        return defaults
    try:
        raw = json.loads(row.value)
    except (TypeError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    for field in allowed_fields.intersection(raw):
        value = raw[field]
        if mapping is None and field == "meta_manufacturer":
            defaults[field] = (
                str(value).strip()
                if value in DOCUMENT_MANUFACTURERS
                else DEFAULT_DOCUMENT_MANUFACTURER
            )
        elif mapping is not None and mapping.fields[field].type == "string_list":
            if isinstance(value, list):
                defaults[field] = [str(item).strip() for item in value if str(item).strip()]
            elif isinstance(value, str) and value.strip():
                defaults[field] = [
                    item.strip() for item in value.split(",") if item.strip()
                ]
            else:
                defaults[field] = []
        elif isinstance(value, str):
            defaults[field] = value.strip() or None
        else:
            defaults[field] = value
    return defaults


def save_document_context_defaults(
    db: Session,
    values: dict[str, object],
    mapping: ClientMapping | None = None,
) -> None:
    """Remember the explicitly patched values for the next document import."""
    current = get_document_context_defaults(db, mapping)
    fields = set(mapping.fields) if mapping is not None else set(DOCUMENT_CONTEXT_FIELDS)
    for field in fields:
        if field not in values:
            continue
        value = values[field]
        if mapping is None and field == "meta_manufacturer":
            current[field] = (
                str(value).strip()
                if value in DOCUMENT_MANUFACTURERS
                else DEFAULT_DOCUMENT_MANUFACTURER
            )
        elif mapping is not None and mapping.fields[field].type == "string_list":
            if isinstance(value, list):
                current[field] = [str(item).strip() for item in value if str(item).strip()]
            elif isinstance(value, str):
                current[field] = [
                    item.strip() for item in value.split(",") if item.strip()
                ]
            else:
                current[field] = []
        elif isinstance(value, str):
            current[field] = value.strip() or None
        else:
            current[field] = value
    serialized = json.dumps(current, ensure_ascii=False, sort_keys=True)
    row = db.get(AppConfig, _DOCUMENT_CONTEXT_DEFAULTS_KEY)
    if row is None:
        db.add(AppConfig(key=_DOCUMENT_CONTEXT_DEFAULTS_KEY, value=serialized))
    else:
        row.value = serialized
    db.commit()
