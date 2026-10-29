"""Manual page type / document page corrections for the preparation step."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.checks.thales_rules.section_detection import (
    DEFAULT_PREPARATION_TITLES,
    SECTION_PAGE_TYPES,
    page_type_for_title,
    page_types_for_titles,
)
from app.core.compiled_rules import CompiledRule
from app.core.errors import AppError
from app.db.models import AppConfig
from app.db.preparation_models import DocumentPreparation, PreparationChecklist

_DOCUMENT_PAGE_RE = re.compile(r"^(?=.*[A-Za-z0-9])[A-Za-z0-9][A-Za-z0-9 ./-]{0,19}$")
_PREPARATION_TITLE_CONFIG_PREFIX = "prep_titles:"


def collect_rule_page_types(rules: Iterable[Any]) -> set[str]:
    page_types: set[str] = set()
    for rule in rules:
        target = rule.target
        if target.page_type is not None:
            page_types.add(target.page_type)
        page_types.update(target.page_types or ())
    return page_types


def preparation_rules(db: Session, bundle: Any) -> list[CompiledRule]:
    """Compiled preparation rules of the client plus the imported checklist."""
    rules = [
        definition.compiled_rule for definition in bundle.rules if definition.preparation
    ]
    checklist = db.get(PreparationChecklist, bundle.client_code)
    if checklist is not None:
        try:
            items = json.loads(checklist.rules_json)
        except ValueError as exc:
            raise AppError(
                "PREPARATION_STATE_INVALID",
                "L'état de préparation (rules_json) est illisible.",
                status_code=500,
            ) from exc
        rules.extend(CompiledRule.model_validate(item) for item in items)
    return rules


def available_page_types(db: Session, bundle: Any) -> list[str]:
    """Page types targeted by the client's preparation rules and imported checklist."""
    page_types = collect_rule_page_types(preparation_rules(db, bundle))
    if bundle.client_code == "THALES":
        page_types.update(SECTION_PAGE_TYPES)
        page_types.update(
            page_types_for_titles(
                load_preparation_page_titles(db, bundle.client_code)
            ).values()
        )
    return sorted(page_types)


def available_page_title_options(db: Session, bundle: Any) -> list[dict[str, str]]:
    if bundle.client_code != "THALES":
        return []
    return [
        {"title": title, "page_type": page_type_for_title(title)}
        for title in load_preparation_page_titles(db, bundle.client_code)
    ]


def load_preparation_page_titles(db: Session, client_code: str) -> list[str]:
    row = db.get(AppConfig, f"{_PREPARATION_TITLE_CONFIG_PREFIX}{client_code}")
    if row is None:
        return list(DEFAULT_PREPARATION_TITLES)
    try:
        value = json.loads(row.value)
    except (TypeError, ValueError) as exc:
        raise AppError(
            "PREPARATION_TITLES_INVALID",
            "La liste des titres de préparation est illisible.",
            status_code=500,
        ) from exc
    if not isinstance(value, list):
        raise AppError(
            "PREPARATION_TITLES_INVALID",
            "La liste des titres de préparation est invalide.",
            status_code=500,
        )
    try:
        return _normalize_preparation_page_titles(value, status_code=500)
    except AppError as exc:
        raise AppError(
            "PREPARATION_TITLES_INVALID",
            "La liste des titres de préparation est invalide.",
            status_code=500,
        ) from exc


def save_preparation_page_titles(
    db: Session,
    client_code: str,
    titles: list[str],
) -> list[str]:
    normalized = _normalize_preparation_page_titles(titles)
    config_key = f"{_PREPARATION_TITLE_CONFIG_PREFIX}{client_code}"
    row = db.get(AppConfig, config_key)
    serialized = json.dumps(normalized, ensure_ascii=False)
    if row is None:
        db.add(AppConfig(key=config_key, value=serialized))
    else:
        row.value = serialized
    db.commit()
    return normalized


def _normalize_preparation_page_titles(
    titles: list[Any],
    *,
    status_code: int = 422,
) -> list[str]:
    if len(titles) > 200:
        raise AppError(
            "PREPARATION_TITLES_INVALID",
            "La liste ne peut pas contenir plus de 200 titres.",
            status_code=status_code,
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for title in titles:
        if not isinstance(title, str):
            raise AppError(
                "PREPARATION_TITLE_INVALID",
                "Chaque titre doit être une chaîne de caractères.",
                status_code=status_code,
            )
        value = " ".join(title.split())
        if (
            not 2 <= len(value) <= 80
            or any(ord(character) < 32 for character in title)
        ):
            raise AppError(
                "PREPARATION_TITLE_INVALID",
                "Chaque titre doit contenir entre 2 et 80 caractères sur une seule ligne.",
                status_code=status_code,
            )
        key = value.casefold()
        if key in seen:
            raise AppError(
                "PREPARATION_TITLE_DUPLICATE",
                "La liste contient un titre en double.",
                status_code=status_code,
            )
        seen.add(key)
        normalized.append(value)
    return normalized


def required_page_type_groups(rules: Iterable[CompiledRule]) -> list[list[str]]:
    """Page types the rules need; a `page_types` list is satisfied by any of its members."""
    groups: set[tuple[str, ...]] = set()
    for rule in rules:
        target = rule.target
        if target.page_type is not None:
            groups.add((target.page_type,))
        if target.page_types:
            groups.add(tuple(target.page_types))
    return [list(group) for group in sorted(groups)]


def load_absent_page_types(record: DocumentPreparation) -> list[str]:
    try:
        value = json.loads(record.absent_page_types_json or "[]")
    except ValueError:
        value = None
    if not isinstance(value, list):
        raise AppError(
            "PREPARATION_STATE_INVALID",
            "L'état de préparation (absent_page_types_json) est illisible.",
            status_code=500,
        )
    return [str(item) for item in value]


def set_absent_page_types(
    db: Session,
    record: DocumentPreparation,
    page_types: list[str],
    absent: bool,
    allowed_page_types: Iterable[str],
) -> list[str]:
    """Declare a required section as not present in the document (or undo it)."""
    allowed = set(allowed_page_types)
    if not page_types or any(page_type not in allowed for page_type in page_types):
        raise AppError(
            "PAGE_TYPE_INVALID",
            "Ce type de page n'est pas proposé pour ce client.",
            status_code=422,
        )
    current = set(load_absent_page_types(record))
    current = current | set(page_types) if absent else current - set(page_types)
    record.absent_page_types_json = json.dumps(sorted(current))
    record.updated_at = datetime.now(UTC)
    db.commit()
    return sorted(current)


def page_requirements(
    db: Session,
    bundle: Any,
    record: DocumentPreparation,
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Required page types still to provide, declared absent, and the rules skipped for it.

    Empty until a detection has run.
    """
    if not decisions:
        return {"missing_page_types": [], "absent_page_types": [], "skipped_rules": []}
    present = {decision.get("page_type") for decision in decisions}
    absent = set(load_absent_page_types(record))
    rules = preparation_rules(db, bundle)
    missing: list[list[str]] = []
    absent_groups: list[list[str]] = []
    for group in required_page_type_groups(rules):
        if present.intersection(group):
            continue
        (absent_groups if set(group) <= absent else missing).append(group)
    absent_keys = {tuple(group) for group in absent_groups}
    skipped: dict[str, dict[str, Any]] = {}
    for rule in rules:
        target = rule.target
        needed = [
            group
            for group in ((target.page_type,), tuple(target.page_types or ()))
            if group and group[0]
        ]
        hit = next((group for group in needed if group in absent_keys), None)
        if hit is not None and rule.id not in skipped:
            skipped[rule.id] = {"rule_id": rule.id, "title": rule.topic, "page_types": list(hit)}
    return {
        "missing_page_types": missing,
        "absent_page_types": absent_groups,
        "skipped_rules": list(skipped.values()),
    }


def load_page_classification(record: DocumentPreparation) -> dict[str, dict[str, str | None]]:
    try:
        value = json.loads(record.page_classification_json or "{}")
    except ValueError as exc:
        raise AppError(
            "PREPARATION_STATE_INVALID",
            "L'état de préparation (page_classification_json) est illisible.",
            status_code=500,
        ) from exc
    if not isinstance(value, dict):
        raise AppError(
            "PREPARATION_STATE_INVALID",
            "L'état de préparation (page_classification_json) est illisible.",
            status_code=500,
        )
    return value


def normalize_document_page(value: str | None) -> str | None:
    if value is None:
        return None
    compact = " ".join(value.split())
    if not compact:
        return None
    if not _DOCUMENT_PAGE_RE.fullmatch(compact):
        raise AppError(
            "DOCUMENT_PAGE_INVALID",
            "Le numéro de page documentaire est invalide.",
            status_code=422,
        )
    return compact


def set_page_classification(
    db: Session,
    record: DocumentPreparation,
    page_number: int,
    page_type: str | None,
    document_page: str | None,
    allowed_page_types: Iterable[str],
    allowed_page_title_options: Iterable[Mapping[str, str]],
    page_title: str | None = None,
) -> dict[str, str | None] | None:
    """Store a manual correction; both values empty reverts to automatic detection."""
    if not 1 <= page_number <= record.page_count:
        raise AppError("PAGE_RANGE_INVALID", "Numéro de page invalide.", status_code=422)
    if page_type is not None and page_type not in set(allowed_page_types):
        raise AppError(
            "PAGE_TYPE_INVALID",
            "Ce type de page n'est pas proposé pour ce client.",
            status_code=422,
        )
    title_types = {
        option["title"]: option["page_type"]
        for option in allowed_page_title_options
    }
    if page_title is not None and (
        page_type is None or title_types.get(page_title) != page_type
    ):
        raise AppError(
            "PAGE_TITLE_INVALID",
            "Ce titre n'est pas proposé pour le type de page sélectionné.",
            status_code=422,
        )
    document_page = normalize_document_page(document_page)
    classification = load_page_classification(record)
    entry: dict[str, str | None] | None = None
    if page_type is None and document_page is None and page_title is None:
        classification.pop(str(page_number), None)
    else:
        entry = {"page_type": page_type, "document_page": document_page}
        if page_title is not None:
            entry["page_title"] = page_title
        classification[str(page_number)] = entry
    if page_type is not None:
        absent = [item for item in load_absent_page_types(record) if item != page_type]
        record.absent_page_types_json = json.dumps(absent)
    record.page_classification_json = json.dumps(classification, ensure_ascii=False)
    record.updated_at = datetime.now(UTC)
    db.commit()
    return entry


def reset_page_decisions(record: DocumentPreparation) -> None:
    """Drop computed decisions whose inputs (OCR text, mapping) changed; caller commits."""
    record.page_decisions_json = "[]"
