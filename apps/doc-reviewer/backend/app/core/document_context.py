"""Runtime metadata required before a document analysis can start."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AppConfig


REQUIRED_DOCUMENT_CONTEXT_FIELDS = (
    "meta_revision_date",
    "meta_cmm_number",
    "meta_first_issue_date",
    "meta_revision_number",
    "document_language",
)

_DOCUMENT_CONTEXT_DEFAULTS_KEY = "document.context_defaults"


def missing_document_context(document: Any) -> list[str]:
    """Return required document metadata fields that are empty at runtime."""
    return [
        field
        for field in REQUIRED_DOCUMENT_CONTEXT_FIELDS
        if not str(getattr(document, field, "") or "").strip()
    ]


def get_document_context_defaults(db: Session) -> dict[str, str | None]:
    """Return the context copied onto newly imported documents."""
    row = db.get(AppConfig, _DOCUMENT_CONTEXT_DEFAULTS_KEY)
    if row is None or not row.value:
        return {field: None for field in REQUIRED_DOCUMENT_CONTEXT_FIELDS}
    try:
        raw = json.loads(row.value)
    except (TypeError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        field: str(raw[field]).strip() if raw.get(field) not in (None, "") else None
        for field in REQUIRED_DOCUMENT_CONTEXT_FIELDS
    }


def save_document_context_defaults(
    db: Session,
    values: dict[str, object],
) -> None:
    """Remember the explicitly patched values for the next document import."""
    current = get_document_context_defaults(db)
    for field in REQUIRED_DOCUMENT_CONTEXT_FIELDS:
        if field not in values:
            continue
        value = values[field]
        current[field] = str(value).strip() if value not in (None, "") else None
    serialized = json.dumps(current, ensure_ascii=False, sort_keys=True)
    row = db.get(AppConfig, _DOCUMENT_CONTEXT_DEFAULTS_KEY)
    if row is None:
        db.add(AppConfig(key=_DOCUMENT_CONTEXT_DEFAULTS_KEY, value=serialized))
    else:
        row.value = serialized
    db.commit()
