"""Compatibility helpers for built-in catalogs stored as CompiledRule JSON."""

from __future__ import annotations

from typing import Any

from app.core.compiled_rules import CompiledRule


_COMPILED_FIELDS = frozenset(CompiledRule.model_fields)


def serialize_compiled_rule(
    rule: CompiledRule,
    presentation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a compiled rule while preserving the legacy catalog view."""
    payload = rule.model_dump(mode="json")
    first_check = rule.checks[0] if rule.checks else None
    payload["code"] = rule.id
    payload.setdefault("title", rule.topic)
    payload.setdefault("description", "")
    payload.setdefault(
        "kind",
        "regex_flag" if first_check and first_check.operator == "regex" else "field_required",
    )
    payload.setdefault("severity", "warning")
    payload.setdefault("pattern", str(first_check.expected or "") if first_check else "")
    payload.setdefault("replacement", "")
    payload.setdefault("message", rule.topic)
    payload.setdefault("example_invalid", "")
    payload.setdefault("example_valid", "")
    payload.setdefault("metadata", {})
    if presentation:
        payload.update(presentation)
    return payload


def compiled_rule_from_payload(
    payload: dict[str, Any],
    *,
    origin_ref: str | None = None,
) -> CompiledRule:
    """Read only CompiledRule fields from a catalog payload.

    Built-in catalog JSON may contain presentation fields for backwards
    compatibility. Strict validation is deliberately applied to the compiled
    subset only.
    """
    core = {key: payload[key] for key in _COMPILED_FIELDS if key in payload}
    rule = CompiledRule.model_validate(core)
    presentation_replacement = payload.get("replacement")
    if (
        isinstance(presentation_replacement, str)
        and presentation_replacement
        and rule.checks
        and rule.checks[0].operator in {"regex", "not_exists", "contains_none"}
        and rule.checks[0].replacement is None
    ):
        checks = list(rule.checks)
        checks[0] = checks[0].model_copy(update={"replacement": presentation_replacement})
        rule = rule.model_copy(update={"checks": checks})
    if origin_ref is not None:
        rule = rule.model_copy(update={"origin_ref": origin_ref})
    return rule


def catalog_rule_view(
    payload: dict[str, Any],
    presentation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the legacy API shape for a compiled catalog entry."""
    rule = compiled_rule_from_payload(payload)
    first_check = rule.checks[0] if rule.checks else None
    view: dict[str, Any] = {
        "code": rule.id,
        "title": rule.topic,
        "description": "",
        "description_en": None,
        "kind": "regex_flag" if first_check and first_check.operator == "regex" else "field_required",
        "severity": "warning",
        "pattern": str(first_check.expected or "") if first_check else "",
        "replacement": "",
        "message": rule.topic,
        "message_en": None,
        "example_invalid": "",
        "example_valid": "",
        "metadata": {},
    }
    for key in (
        "code",
        "title",
        "description",
        "description_en",
        "kind",
        "severity",
        "pattern",
        "replacement",
        "message",
        "message_en",
        "example_invalid",
        "example_valid",
        "metadata",
    ):
        if key in payload:
            view[key] = payload[key]
    if presentation:
        view.update(presentation)
    return view


def is_compiled_catalog_payload(payload: object) -> bool:
    """Whether a catalog entry contains the current strict rule contract."""
    if not isinstance(payload, dict):
        return False
    return all(key in payload for key in ("id", "execution", "target", "checks", "source"))
