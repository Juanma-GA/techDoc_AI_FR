"""Versioned, bilingual requirement proposals stored in the local AppConfig."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from functools import cached_property
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, StringConstraints, TypeAdapter, ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import AppError
from app.core.preliminary_rule_defaults import Category, default_entries
from app.core.procedure_semantics import REQUIREMENT_CATEGORIES, heading_label, heading_scope, normalize
from app.db.models import AppConfig

CONFIG_KEY = "preliminary_rules"
Expression = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\r\n\t]+$"),
]


class RuleGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    category: Category
    kind: Literal["keyword", "heading"]
    fr: list[Expression] = Field(min_length=1, max_length=1000)
    en: list[Expression] = Field(min_length=1, max_length=1000)


class _LegacyRule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    category: Category
    kind: Literal["keyword", "heading"]
    fr: Expression
    en: Expression


class _LegacyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    revision: int = Field(ge=0)
    rules: list[_LegacyRule] = Field(max_length=1000)


class RulesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    revision: int = Field(ge=0)
    groups: list[RuleGroup] = Field(max_length=12)


class RulesConfig(RulesUpdate):
    _stored_value: str | None = PrivateAttr(default=None)
    _legacy_fingerprint: str | None = PrivateAttr(default=None)

    @cached_property
    def fingerprint(self) -> str:
        return self._legacy_fingerprint or hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    @cached_property
    def headings(self) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for group in self.groups:
            if group.kind == "heading":
                result.setdefault(group.category, set()).update(
                    heading_label(value)
                    for value in (*group.fr, *group.en)
                )
        return result

    @cached_property
    def keywords(self) -> dict[str, re.Pattern[str]]:
        groups: dict[str, set[str]] = {}
        for group in self.groups:
            if group.kind == "keyword":
                groups.setdefault(group.category, set()).update(normalize(value) for value in (*group.fr, *group.en))
        return {
            category: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(term) for term in sorted(terms)) + r")(?!\w)")
            for category, terms in groups.items()
        }

    def unchanged_condition(self) -> ColumnElement[bool]:
        stored = select(AppConfig.value).where(AppConfig.key == CONFIG_KEY).scalar_subquery()
        return stored.is_(None) if self._stored_value is None else stored == self._stored_value


def _ordered(groups: Sequence[RuleGroup]) -> list[RuleGroup]:
    return sorted(groups, key=lambda group: (REQUIREMENT_CATEGORIES.index(group.category), group.kind == "heading"))


def _group_legacy(entries: Sequence[_LegacyRule]) -> list[RuleGroup]:
    result: dict[tuple[Category, Literal["keyword", "heading"]], dict[str, list[str]]] = {}
    seen: dict[tuple[Category, str, str], set[str]] = {}
    for entry in entries:
        languages = result.setdefault((entry.category, entry.kind), {"fr": [], "en": []})
        for language, value in (("fr", entry.fr), ("en", entry.en)):
            normalized = heading_label(value) if entry.kind == "heading" else normalize(value)
            terms = seen.setdefault((entry.category, entry.kind, language), set())
            if normalized not in terms:
                terms.add(normalized)
                languages[language].append(value)
    return _ordered([
        RuleGroup(category=category, kind=kind, fr=languages["fr"], en=languages["en"])
        for (category, kind), languages in result.items()
    ])


def _from_legacy(legacy: _LegacyConfig) -> RulesConfig:
    config = RulesConfig(revision=legacy.revision, groups=_group_legacy(legacy.rules))
    # Regrouping unchanged expressions must not invalidate existing reviews.
    config._legacy_fingerprint = hashlib.sha256(legacy.model_dump_json().encode()).hexdigest()
    return config


def defaults() -> RulesConfig:
    return _from_legacy(_LegacyConfig(
        revision=0, rules=[_LegacyRule(**entry) for entry in default_entries()],
    ))


def read_rules(db: Session) -> RulesConfig:
    value = db.scalar(select(AppConfig.value).where(AppConfig.key == CONFIG_KEY))
    if value is None:
        return defaults()
    try:
        stored = TypeAdapter(RulesConfig | _LegacyConfig).validate_json(value)
    except ValidationError as exc:
        raise AppError(
            "RULES_STORAGE_INVALID", "Les regles enregistrees sont invalides. Restaurez leur configuration.", 500,
        ) from exc
    config = RulesConfig(revision=stored.revision, groups=_ordered(stored.groups)) \
        if isinstance(stored, RulesConfig) else _from_legacy(stored)
    config._stored_value = value
    return config


def _validate_groups(groups: list[RuleGroup]) -> None:
    owners: dict[tuple[str, str], str] = {}
    keys = set()
    for count in (sum(len(group.fr) for group in groups), sum(len(group.en) for group in groups)):
        if count > 1000:
            raise AppError("RULES_TOO_MANY", "Limite de 1000 expressions par langue depassee.", 422)
    for group in groups:
        key = (group.kind, group.category)
        if key in keys:
            raise AppError("RULES_DUPLICATE", "Une seule liste par categorie et type est autorisee.", 422)
        keys.add(key)
        for language, values in (("fr", group.fr), ("en", group.en)):
            seen = set()
            for value in values:
                term = normalize(value) if group.kind == "keyword" else heading_label(value)
                if group.kind == "heading" and (
                    not term or heading_scope(value, headings={})[0] != "unknown"
                ):
                    raise AppError(
                        "RULES_RESERVED_HEADING",
                        "Les titres de structure S1000D ne sont pas des titres de categorie modifiables.", 422,
                    )
                if term in seen:
                    raise AppError(
                        "RULES_DUPLICATE", "Une expression figure plusieurs fois dans la meme liste.", 422,
                        detail={"category": group.category, "kind": group.kind, "language": language, "expression": value},
                    )
                seen.add(term)
                previous = owners.setdefault((group.kind, term), group.category)
                if previous != group.category:
                    raise AppError(
                        "RULES_CATEGORY_CONFLICT", "Une expression identique appartient deja a une autre categorie.",
                        422, detail={"expression": value, "category": previous},
                    )


def write_rules(db: Session, payload: RulesUpdate) -> RulesConfig:
    _validate_groups(payload.groups)
    current = read_rules(db)
    if payload.revision != current.revision:
        raise AppError("RULES_CONFLICT", "Les regles ont change. Rechargez avant de les modifier.", 409)
    ordered = _ordered(payload.groups)
    if ordered == current.groups:
        return current
    saved = RulesConfig(revision=current.revision + 1, groups=ordered)
    encoded = saved.model_dump_json()
    if current._stored_value is None:
        db.add(AppConfig(key=CONFIG_KEY, value=encoded))
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise AppError("RULES_CONFLICT", "Une autre sauvegarde a modifie les regles. Rechargez.", 409) from exc
    else:
        result = db.execute(
            update(AppConfig).where(
                AppConfig.key == CONFIG_KEY, AppConfig.value == current._stored_value,
            ).values(value=encoded),
            execution_options={"synchronize_session": False},
        )
        if result.rowcount != 1:
            db.rollback()
            raise AppError("RULES_CONFLICT", "Une autre sauvegarde a modifie les regles. Rechargez.", 409)
        db.commit()
    saved._stored_value = encoded
    return saved
