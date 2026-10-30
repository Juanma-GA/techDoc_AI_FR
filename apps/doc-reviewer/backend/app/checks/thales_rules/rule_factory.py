"""Rule factory shared by every THALES norm (ATA100, S1000D, ...)."""

from __future__ import annotations

from typing import Literal

from app.checks.client_bundle import ClientRuleDefinition
from app.core.compiled_rules import (
    Check,
    CompiledRule,
    Condition,
    RuleExample,
    RulePrerequisite,
    RuleTarget,
)


def build_rule(
    standard_code: str,
    catalog_version: str,
    *,
    code: str,
    name: str,
    description: str,
    message: str,
    kind: str,
    severity: Literal["info", "warning", "error"],
    presentation_severity: Literal["info", "warning", "error"] | None = None,
    target: RuleTarget,
    checks: list[Check],
    failure_message: str | None = None,
    only_if: Condition | None = None,
    valid_examples: list[RuleExample] | None = None,
    invalid_examples: list[RuleExample] | None = None,
    prerequisites: list[RulePrerequisite] | None = None,
    preparation: bool = False,
    translations: dict[str, dict[str, str]] | None = None,
) -> ClientRuleDefinition:
    """Build one rule definition of the catalog `standard_code:catalog_version`.

    Each norm binds its own catalog with `functools.partial(build_rule, code, version)`.
    """
    compiled_rule = CompiledRule(
        id=code,
        topic=name,
        failure_message=failure_message,
        severity=severity,
        execution="deterministic",
        target=target,
        checks=checks,
        source="standard_rule",
        origin_ref=f"{standard_code}:{catalog_version}:{code}",
        only_if=only_if,
        valid_examples=valid_examples or [],
        invalid_examples=invalid_examples or [],
        prerequisites=prerequisites or [],
    )
    return ClientRuleDefinition(
        compiled_rule=compiled_rule,
        name=name,
        description=description,
        message=message,
        kind=kind,
        presentation_severity=presentation_severity,
        preparation=preparation,
        translations=translations or {},
    )
