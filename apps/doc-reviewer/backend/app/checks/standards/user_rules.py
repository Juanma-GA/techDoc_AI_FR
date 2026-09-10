"""Local rules maintained for Doc Reviewer experiments.

Add or remove ``_regex_rule(...)`` entries in ``_RULES_V1`` and restart the
backend. The catalog is synchronized into the local database at startup.
"""

from __future__ import annotations

from typing import Literal

from app.core.compiled_rules import Check, CompiledRule, FieldRef, RuleTarget


STANDARD_CODE = "ATEXIS-CUSTOM"
STANDARD_LABEL = "ATEXIS - Regles utilisateur"
STANDARD_DESCRIPTION = (
    "Regles locales editables pour tester des controles sur les documents."
)

_TARGET = RuleTarget(page="all", region="full_page")
_FOOTER_TARGET = RuleTarget(page="all", region="footer")
_TITLE_PAGE_FOOTER_TARGET = RuleTarget(page="1", region="footer")
_ORIGIN = f"{STANDARD_CODE}:v1"
_CMM_NUMBER_PATTERN = r"\d{2}-\d{2}-\d{2}"
_EXPECTED_CMM_PATTERN = r"(?<!\w){{meta_cmm_number}}(?!\w)"
_COPYRIGHT_START_YEAR = "1966"
_TITLE_PAGE_COPYRIGHT_PATTERN = (
    r"\u00a9\s*\d{4}\s*-\s*\d{4}\s+"
    r"THALES\s+AVS\s+FRANCE\s+SAS\.\s+"
    r"This\s+document\s+and\s+any\s+data\s+included\s+are\s+the\s+property\s+of\s+"
    r"THALES\s+AVS\s+FRANCE\s+SAS\.\s+"
    r"They\s+cannot\s+be\s+reproduced,\s+disclosed\s+or\s+used\s+"
    r"without\s+the\s+company's\s+prior\s+written\s+approval\.?"
)


def _regex_rule(
    code: str,
    topic: str,
    pattern: str,
    *,
    operator: Literal["regex", "regex_exists"] = "regex",
    severity: Literal["info", "warning", "error"] = "warning",
) -> CompiledRule:
    return CompiledRule(
        id=code,
        topic=topic,
        severity=severity,
        execution="deterministic",
        target=_TARGET,
        checks=[Check(field="text", operator=operator, expected=pattern)],
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:{code}",
    )


_RULES_V1 = [
    CompiledRule(
        id="CUSTOM_CMM_NUMBER",
        topic="Numero CMM conforme au contexte du document",
        severity="error",
        execution="deterministic",
        target=_FOOTER_TARGET,
        checks=[
            Check(
                field="text",
                operator="regex_exists",
                expected=_EXPECTED_CMM_PATTERN,
            ),
            Check(
                field="text",
                operator="regex",
                expected=(
                    r"(?<!\w)(?!{{meta_cmm_number}}(?!\w))"
                    + _CMM_NUMBER_PATTERN
                    + r"(?!\w)"
                ),
                replacement="{{meta_cmm_number}}",
            ),
        ],
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:CUSTOM_CMM_NUMBER",
    ),
    CompiledRule(
        id="CUSTOM_TITLE_PAGE_COPYRIGHT",
        topic="Copyright de la title page conforme a l'annee de revision",
        severity="error",
        execution="deterministic",
        target=_FOOTER_TARGET,
        checks=[
            Check(
                field="text",
                operator="regex_exists",
                expected=_TITLE_PAGE_COPYRIGHT_PATTERN,
            ),
            Check(
                field="copyright_start_year",
                operator="normalized_equals",
                expected=_COPYRIGHT_START_YEAR,
                normalization=["trim"],
            ),
            Check(
                field="copyright_end_year",
                operator="equals_field",
                compare_to=FieldRef(
                    source="document_meta",
                    field="meta_revision_date",
                    normalization=["extract_year"],
                ),
            ),
        ],
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:CUSTOM_TITLE_PAGE_COPYRIGHT",
    ),
]


def _default_metadata(rule: CompiledRule) -> dict[str, object]:
    operator = rule.checks[0].operator if rule.checks else "regex"
    return {
        "description": rule.topic,
        "kind": "field_required" if operator == "regex_exists" else "regex_flag",
        "severity": rule.severity,
        "message": rule.topic,
    }


RULE_METADATA = {rule.id: _default_metadata(rule) for rule in _RULES_V1}
RULE_METADATA["CUSTOM_CMM_NUMBER"] = {
    "description": (
        "Le numero present dans le document doit correspondre a la valeur "
        "meta_cmm_number saisie dans le contexte du document."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Le numero CMM ne correspond pas au contexte du document.",
}
RULE_METADATA["CUSTOM_TITLE_PAGE_COPYRIGHT"] = {
    "description": (
        "Le footer de la title page doit contenir le copyright THALES avec "
        "l'annee de debut 1966 et l'annee de revision du document."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Le copyright de la title page est absent ou une annee est incorrecte.",
}


CATALOG: dict[str, list[CompiledRule]] = {"v1": _RULES_V1}


USER_STANDARD_SPEC: dict[str, object] = {
    "code": STANDARD_CODE,
    "label": STANDARD_LABEL,
    "description": STANDARD_DESCRIPTION,
    "versions": CATALOG,
    "metadata": RULE_METADATA,
}