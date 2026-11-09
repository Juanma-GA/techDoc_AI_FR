"""Supported S1000D tag choices for human procedural review."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any

from app.core.s1000d_guide import load_guide

_REQUIREMENT_TAGS = {
    "conditions": ("reqCondNoRef", "noConds"),
    "personnel": ("personnel", "personCategory", "personSkill"),
    "support": (
        "reqSupportEquips", "noSupportEquips", "supportEquipDescr", "name", "identNumber",
        "manufacturerCode", "partAndSerialNumber", "partNumber", "reqQuantity",
    ),
    "supplies": (
        "reqSupplies", "noSupplies", "name", "identNumber", "manufacturerCode",
        "partAndSerialNumber", "partNumber", "reqQuantity",
    ),
    "spares": (
        "reqSpares", "noSpares", "spareDescrGroup", "spareDescr", "name", "identNumber",
        "manufacturerCode", "partAndSerialNumber", "partNumber", "reqQuantity",
    ),
    "safety": ("warning", "caution", "note"),
    "closing": ("reqCondNoRef", "noConds"),
}
_SAFETY_TAGS = ("warning", "caution", "note")
_NO_REQUIREMENT_TAGS = {"noConds", "noSupportEquips", "noSupplies", "noSpares"}
_NO_REQUIREMENT_PREFIX = re.compile(
    r"^(?:no\b|none\b|not required\b|not applicable\b|"
    r"aucun(?:e|s|es)?\b|pas de\b|sans\b)"
)
_WORKBOOK_TO_SCHEMA_TAGS = {"noSuppEquips": "noSupportEquips"}


@lru_cache(maxsize=1)
def _procedural_tags() -> frozenset[str]:
    tags = {
        component
        for rule in load_guide().rules_for("procedural")
        for component in rule.components
    }
    # The workbook spelling conflicts with the S1000D XSD element name.
    tags.update(
        schema_tag
        for workbook_tag, schema_tag in _WORKBOOK_TO_SCHEMA_TAGS.items()
        if workbook_tag in tags
    )
    return frozenset(tags)


def _is_no_requirement(text: str) -> bool:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in decomposed if not unicodedata.combining(char))
    return bool(_NO_REQUIREMENT_PREFIX.match(re.sub(r"[^a-z0-9]+", " ", normalized).strip()))


def tag_options_for(passage: dict[str, Any]) -> dict[str, list[str]]:
    if passage.get("role", "content") != "content":
        return {}

    procedural_tags = _procedural_tags()
    no_requirement = _is_no_requirement(
        passage.get("text") or passage.get("source_text") or "",
    )
    kind = passage.get("kind")
    common_tags: tuple[str, ...]
    body_tags: tuple[str, ...]
    if kind == "paragraph":
        common_tags, body_tags = ("para",), ("proceduralStep",)
    elif kind == "admonition":
        admonition = passage.get("admonition")
        selected = admonition if admonition in _SAFETY_TAGS else "note"
        common_tags = body_tags = (selected,)
    elif kind == "item":
        common_tags = body_tags = ("para",)
    elif kind == "item-sequence":
        ordered = passage.get("form") == "ordered"
        common_tags = ("sequentialList",) if ordered else ("randomList",)
        body_tags = ("proceduralStep",) if ordered else ("randomList",)
    elif kind == "table":
        common_tags = body_tags = ("table",)
    else:
        common_tags = body_tags = ()
    return {
        **{
            category: [
                tag for tag in tags
                if tag in procedural_tags and (tag not in _NO_REQUIREMENT_TAGS or no_requirement)
            ]
            for category, tags in _REQUIREMENT_TAGS.items()
        },
        "common": [tag for tag in common_tags if tag in procedural_tags],
        "body": [tag for tag in body_tags if tag in procedural_tags],
        "discard": [],
    }


def default_tag_for(destination: str | None, passage: dict[str, Any]) -> str | None:
    if not isinstance(destination, str) or destination == "discard":
        return None

    options = tag_options_for(passage).get(destination, [])
    preferred = {
        "conditions": "reqCondNoRef",
        "personnel": "personnel",
        "support": "supportEquipDescr",
        "supplies": "reqSupplies",
        "spares": "spareDescr",
        "closing": "reqCondNoRef",
    }.get(destination)
    if destination == "safety":
        preferred = passage.get("admonition") or "note"
    elif destination in {"body", "common"}:
        kind = passage.get("kind")
        if kind == "paragraph":
            preferred = "proceduralStep" if destination == "body" else "para"
        elif kind == "admonition":
            preferred = passage.get("admonition") or "note"
        elif isinstance(kind, str):
            preferred = {
                "item": "para",
                "item-sequence": "randomList",
                "table": "table",
            }.get(kind)

    return preferred if preferred in options else (options[0] if options else None)


def target_tag_validation_error(
    destination: str | None,
    tag: str | None,
    passage: dict[str, Any],
) -> str | None:
    if destination == "discard":
        return None if tag is None else "Une balise ne peut pas etre affectee a un passage ecarte."
    if destination is None:
        return "Choisissez une categorie avant d'affecter une balise."
    if tag in _NO_REQUIREMENT_TAGS:
        if not _is_no_requirement(passage.get("text") or passage.get("source_text") or ""):
            return "Cette balise indique qu'aucune exigence n'est requise; le contenu doit le preciser."
    if tag not in tag_options_for(passage).get(destination, []):
        return "Choisissez une balise proposee pour la categorie selectionnee."
    return None


def valid_target_tag(destination: str | None, tag: str | None, passage: dict[str, Any]) -> bool:
    return target_tag_validation_error(destination, tag, passage) is None


def template_key(passage: dict[str, Any]) -> tuple[object, ...] | None:
    marker = passage.get("marker_key")
    return ("source-marker", marker) if isinstance(marker, str) and marker else None


def build_template(
    passages: list[dict[str, Any]],
) -> dict[tuple[object, ...], tuple[str, str | None]]:
    choices: dict[tuple[object, ...], tuple[str, str | None]] = {}
    ambiguous: set[tuple[object, ...]] = set()
    for passage in passages:
        key = template_key(passage)
        destination = passage.get("decision")
        tag = passage.get("target_tag")
        if key is None or not isinstance(destination, str) or (tag is not None and not isinstance(tag, str)):
            continue
        if passage.get("role", "content") != "content" or not valid_target_tag(
            destination, tag, passage,
        ):
            continue
        choice = (destination, tag)
        if key in ambiguous:
            continue
        if key in choices and choices[key] != choice:
            choices.pop(key)
            ambiguous.add(key)
        else:
            choices[key] = choice
    return choices


def has_conflicting_tag_choices(passages: list[dict[str, Any]]) -> bool:
    no_tag_by_category = {
        "conditions": "noConds",
        "closing": "noConds",
        "support": "noSupportEquips",
        "supplies": "noSupplies",
        "spares": "noSpares",
    }
    for category, no_tag in no_tag_by_category.items():
        selected = [
            passage.get("target_tag")
            for passage in passages
            if passage.get("role", "content") == "content"
            and passage.get("decision") == category
            and passage.get("target_tag")
        ]
        if no_tag in selected and any(tag != no_tag for tag in selected):
            return True
    return False
