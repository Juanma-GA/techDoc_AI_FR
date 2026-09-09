"""Conservative migration of compatible built-in rules to CompiledRule."""

from __future__ import annotations

from typing import Any

from app.checks.standards._catalog import compiled_rule_from_payload, is_compiled_catalog_payload
from app.core.compiled_rules import Check, CompiledRule, RuleTarget


MIGRATED_REGEX_FLAG_CODES = frozenset(
    {
        "ATA_CHAPTER_REF",
        "ATA_CHAPTER_RANGE",
        "ATA_NO_AMBIGUOUS_QUANT",
        "STE_PASSIVE_VOICE",
        "STE_FIRST_PERSON",
        "STE_PROCEDURAL_GERUND",
        "STE_NO_MAYBE",
        "STE_NO_CONTRACTION",
        "MAT_NO_PASSIVE",
    }
)


def compile_standard_rule(rule: dict[str, Any], origin_ref: str) -> CompiledRule | None:
    """Compile only reviewed regex flags whose match proves a violation."""
    if is_compiled_catalog_payload(rule):
        compiled = compiled_rule_from_payload(rule, origin_ref=origin_ref)
        if compiled.source != "standard_rule":
            return None
        return compiled
    code = str(rule.get("code") or "")
    pattern = str(rule.get("pattern") or "")
    if rule.get("kind") != "regex_flag" or code not in MIGRATED_REGEX_FLAG_CODES or not pattern:
        return None
    return CompiledRule(
        id=code,
        topic=str(rule.get("title") or code),
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[Check(field="text", operator="regex", expected=pattern)],
        source="standard_rule",
        origin_ref=origin_ref,
    )