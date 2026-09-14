"""Strict contracts for deterministic compiled rules and their results."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.primitive_catalog import PRIMITIVE_CATALOG, REFERENCE_CATALOG


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# `extract_year` is a value transform (not a pure text normalization) reused
# by `normalized_equals` and by `FieldRef.normalization` for cross-field
# comparisons: it turns "MAR 18/26" or "© 2000-2026" into "2026" so a
# 2-digit revision year can be compared against a 4-digit copyright year.
NormalizationStep = Literal["unicode", "trim", "spaces", "line_breaks", "extract_year"]

EntityField = Literal[
    "text",
    "page_number",
    "revision_number",
    "revision_date",
    "first_issue_date",
    "copyright_start_year",
    "copyright_end_year",
    "document_type",
]

DocumentMetaField = Literal[
    "meta_revision_date",
    "meta_cmm_number",
    "meta_first_issue_date",
    "meta_revision_number",
    "document_language",
]


class RuleTarget(StrictModel):
    page: str
    region: Literal["full_page", "header", "body", "footer"]
    page_type: str | None = None


class FieldRef(StrictModel):
    """A value to compare against, resolved elsewhere in the document.

    `source="document_text"` re-scopes the parsed document to `page`/`region`
    and reads `field` there (same entities as `Check.field`).
    `source="document_meta"` reads a structured per-document field entered by
    the reviewer (falls back to the checklist settings reference value when
    the document field is empty) — used for e.g. the actual revision date,
    which the parsed text rarely carries verbatim.
    """

    source: Literal["document_text", "document_meta"] = "document_text"
    field: str
    page: str = "all"
    region: Literal["full_page", "header", "body", "footer"] = "full_page"
    normalization: list[NormalizationStep] | None = None

    @model_validator(mode="after")
    def validate_field(self) -> FieldRef:
        allowed = set(get_args(EntityField)) if self.source == "document_text" else set(get_args(DocumentMetaField))
        if self.field not in allowed:
            raise ValueError(f"champ invalide pour source={self.source}: {self.field}")
        return self


class Condition(StrictModel):
    """Gate a rule so it only applies when a document field is present/absent.

    Example: a rule about the CMM number footer should only run when a CMM
    number was actually captured for this document.
    """

    field: DocumentMetaField
    state: Literal["present", "absent"] = "present"


class PrimitiveStep(StrictModel):
    step_id: str = Field(min_length=1, max_length=80)
    primitive: str = Field(min_length=1, max_length=120)
    parameters: dict[str, Any] = Field(default_factory=dict)
    input_from: dict[str, str] = Field(default_factory=dict)


class RuleExample(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    outcome: Literal["valid", "invalid"]
    explanation: str | None = Field(default=None, max_length=500)


class RulePrerequisite(StrictModel):
    reference_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=500)


class Check(StrictModel):
    field: EntityField
    operator: Literal[
        "exists",
        "not_exists",
        "equals",
        "regex",
        "normalized_equals",
        # Term-list variants: cover "forbidden words", "required synonyms" and
        # "all of these must appear" without forcing every checklist line
        # through a hand-built regex (which is where the LLM compiler used to
        # give up and fall back to `semantic`).
        "contains_any",
        "contains_all",
        "contains_none",
        # Cross-field/cross-zone comparison: compare this check's field to a
        # value resolved elsewhere (another region, or a structured document
        # field) instead of a literal `expected`. See `compare_to`.
        "equals_field",
        # `regex` flags a FORBIDDEN pattern (FAIL when found — same idiom as
        # not_exists). `regex_exists` is its mirror for a MANDATORY pattern
        # with a variable part (FAIL when NOT found — same idiom as exists).
        # Compiling "this text must be present" as `regex` inverts the
        # intent and flags the correct text as a violation every time.
        "regex_exists",
    ]
    expected: str | int | list[str] | None = None
    expected_display: str | None = None
    missing_anchor: str | None = None
    missing_anchor_position: Literal["above", "below"] = "above"
    normalization: list[NormalizationStep] | None = None
    # Auto-fix proposals for deterministic FAILs, mirroring the legacy
    # regex_replace/term_replace custom-rule kinds — kept optional because
    # not every deterministic check has an obvious correction.
    replacement: str | None = None
    replacements: dict[str, str] | None = None
    compare_to: FieldRef | None = None
    only_if: Condition | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> Check:
        list_ops = {"contains_any", "contains_all", "contains_none"}
        if self.operator in list_ops:
            if not isinstance(self.expected, list) or not self.expected:
                raise ValueError(f"{self.operator} requires a non-empty list in expected")
        elif self.operator == "equals_field":
            if self.compare_to is None:
                raise ValueError("equals_field requires compare_to")
            if self.expected is not None:
                raise ValueError("equals_field must not set expected")
        else:
            if isinstance(self.expected, list):
                raise ValueError(f"{self.operator} does not accept a list in expected")
        if self.compare_to is not None and self.operator != "equals_field":
            raise ValueError("compare_to is only allowed with equals_field")
        if self.operator == "normalized_equals" and not self.normalization:
            raise ValueError("normalized_equals requires at least one normalization step")
        if self.operator in {"regex", "regex_exists"}:
            if not isinstance(self.expected, str) or not self.expected:
                raise ValueError(f"{self.operator} requires a non-empty regex string")
            try:
                re.compile(self.expected)
            except re.error as exc:
                raise ValueError(f"regex invalide: {exc.msg}") from exc
        if self.missing_anchor is not None:
            try:
                re.compile(self.missing_anchor)
            except re.error as exc:
                raise ValueError(f"missing_anchor invalide: {exc.msg}") from exc
        if self.operator not in {"normalized_equals", "equals_field"} and self.normalization is not None:
            raise ValueError("normalization is only allowed with normalized_equals or equals_field")
        if self.replacement is not None and self.operator not in {"regex", "not_exists", "contains_none"}:
            raise ValueError("replacement is only allowed with regex, not_exists or contains_none")
        if self.replacements is not None and self.operator != "contains_none":
            raise ValueError("replacements is only allowed with contains_none")
        if self.replacement is not None and self.replacements is not None:
            raise ValueError("use either replacement or replacements, not both")
        return self


class PdfEvidenceLocation(StrictModel):
    type: Literal["bbox"] = "bbox"
    bbox: tuple[float, float, float, float]


class DocxEvidenceLocation(StrictModel):
    type: Literal["target_id"] = "target_id"
    target_id: str = Field(min_length=1, max_length=120)


EvidenceLocation = Annotated[
    PdfEvidenceLocation | DocxEvidenceLocation,
    Field(discriminator="type"),
]


class Evidence(StrictModel):
    page: str
    location: EvidenceLocation
    observed_value: str | None
    expected_value: str | None


class CompiledRule(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    topic: str
    failure_message: str | None = None
    severity: Literal["info", "warning", "error"] = "warning"
    execution: Literal["deterministic", "semantic", "manual", "unsupported"]
    target: RuleTarget
    checks: list[Check] = Field(default_factory=list)
    semantic_instruction: str | None = None
    manual_instruction: str | None = None
    compilation_error: str | None = None
    source: Literal["standard_rule", "user_checklist"]
    origin_ref: str | None = Field(default=None, max_length=500)
    source_instruction: str | None = Field(default=None, max_length=2000)
    primitive_plan: list[PrimitiveStep] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    valid_examples: list[RuleExample] = Field(default_factory=list)
    invalid_examples: list[RuleExample] = Field(default_factory=list)
    prerequisites: list[RulePrerequisite] = Field(default_factory=list)
    # Applies to every execution kind: when set and unmet, the whole rule is
    # skipped for this document (e.g. a CMM-number rule on a document that
    # has no CMM number captured) instead of producing a misleading PASS/FAIL.
    only_if: Condition | None = None

    @property
    def code(self) -> str:
        return self.id

    @property
    def pattern(self) -> str | None:
        if len(self.checks) == 1 and self.checks[0].operator == "regex":
            expected = self.checks[0].expected
            return str(expected) if expected is not None else None
        return None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.id,
            "title": self.topic,
            "kind": "regex_flag" if self.pattern is not None else "compiled",
            "pattern": self.pattern,
        }

    @model_validator(mode="after")
    def validate_execution_contract(self) -> CompiledRule:
        if self.primitive_plan:
            definitions = {item.id: item for item in PRIMITIVE_CATALOG}
            known_primitives = set(definitions)
            unknown = sorted({step.primitive for step in self.primitive_plan} - known_primitives)
            if unknown:
                raise ValueError(f"primitive(s) inconnue(s): {', '.join(unknown)}")
            for step in self.primitive_plan:
                allowed_parameters = {parameter.name for parameter in definitions[step.primitive].parameters}
                unknown_parameters = sorted(set(step.parameters) - allowed_parameters)
                if unknown_parameters:
                    raise ValueError(
                        f"parametre(s) inconnu(s) pour {step.primitive}: {', '.join(unknown_parameters)}"
                    )
            known_references = {item.id for item in REFERENCE_CATALOG}
            referenced_ids = {
                prerequisite.reference_id for prerequisite in self.prerequisites
            }
            for step in self.primitive_plan:
                reference_id = step.parameters.get("reference_id")
                if isinstance(reference_id, str):
                    referenced_ids.add(reference_id)
            unknown_references = sorted(referenced_ids - known_references)
            if unknown_references:
                raise ValueError(
                    f"reference(s) inconnue(s): {', '.join(unknown_references)}"
                )
        if self.execution == "manual":
            if not self.manual_instruction:
                raise ValueError("manual execution requires manual_instruction")
            if self.checks:
                raise ValueError("manual execution requires empty checks")
            if self.semantic_instruction is not None:
                raise ValueError("manual execution requires semantic_instruction to be None")
            if self.compilation_error is not None:
                raise ValueError("manual execution requires compilation_error to be None")
        elif self.execution == "semantic":
            if not self.semantic_instruction:
                raise ValueError("semantic execution requires semantic_instruction")
            if self.checks:
                raise ValueError("semantic execution requires empty checks")
            if self.manual_instruction is not None or self.compilation_error is not None:
                raise ValueError(
                    "semantic execution requires manual_instruction and compilation_error to be None"
                )
        elif self.execution == "unsupported":
            if not self.compilation_error:
                raise ValueError("unsupported execution requires compilation_error")
            if self.checks:
                raise ValueError("unsupported execution requires empty checks")
            if self.semantic_instruction is not None or self.manual_instruction is not None:
                raise ValueError(
                    "unsupported execution requires semantic_instruction and manual_instruction to be None"
                )
        else:
            if not self.checks:
                raise ValueError("deterministic execution requires at least one check")
            if self.semantic_instruction is not None:
                raise ValueError("deterministic execution requires semantic_instruction to be None")
            if self.manual_instruction is not None or self.compilation_error is not None:
                raise ValueError(
                    "deterministic execution requires manual_instruction and compilation_error to be None"
                )
        return self


class RuleResult(StrictModel):
    rule_id: str = Field(min_length=1, max_length=120)
    status: Literal["PASS", "FAIL", "MANUAL", "UNSUPPORTED", "INCONCLUSIVE"]
    evidence: Evidence | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> RuleResult:
        if self.status in {"PASS", "FAIL", "INCONCLUSIVE"} and self.evidence is None:
            raise ValueError(f"{self.status} requires evidence")
        if self.status in {"MANUAL", "UNSUPPORTED"} and self.evidence is not None:
            raise ValueError(f"{self.status} requires evidence to be None")
        return self


def compiled_rule_json_schema() -> dict[str, object]:
    return CompiledRule.model_json_schema()


def validate_compiled_rule_json(payload: str | bytes | bytearray) -> CompiledRule:
    """Validate serialized JSON before a rule can be persisted or executed."""
    return CompiledRule.model_validate_json(payload)


def _describe_check(check: Check) -> str:
    if check.operator == "exists":
        return f'{check.field} contient "{check.expected}"' if check.expected is not None else f"{check.field} present"
    if check.operator == "not_exists":
        text = f'{check.field} ne contient pas "{check.expected}"'
        return f'{text} (remplacement propose : "{check.replacement}")' if check.replacement else text
    if check.operator in {"equals", "normalized_equals"}:
        return f'{check.field} = "{check.expected}"'
    if check.operator == "regex":
        text = f"{check.field} correspond a /{check.expected}/ (motif interdit)"
        return f'{text} (remplacement propose : "{check.replacement}")' if check.replacement else text
    if check.operator == "regex_exists":
        return f"{check.field} doit correspondre a /{check.expected}/ (motif obligatoire)"
    if check.operator in {"contains_any", "contains_all", "contains_none"}:
        verb = {
            "contains_any": "contient au moins un de",
            "contains_all": "contient tous les termes",
            "contains_none": "ne contient aucun de",
        }[check.operator]
        terms = ", ".join(str(term) for term in (check.expected or []))
        text = f"{check.field} {verb} : {terms}"
        if check.operator == "contains_none" and (check.replacement or check.replacements):
            text += " (remplacement propose)"
        return text
    if check.operator == "equals_field":
        ref = check.compare_to
        assert ref is not None
        other = f"donnee document {ref.field}" if ref.source == "document_meta" else f"{ref.field} ({ref.page}/{ref.region})"
        return f"{check.field} = {other}"
    return check.field


def describe_compiled_rule(rule: CompiledRule) -> str | None:
    """Human-readable summary of what a compiled rule actually checks.

    Used to fill the UI "Détail" column with something specific to this
    rule instead of a generic placeholder — semantic/manual/unsupported
    rules already carry their own instruction/error text, deterministic
    rules need their checks rendered into a sentence."""
    if rule.execution == "semantic":
        return rule.semantic_instruction
    if rule.execution == "manual":
        return rule.manual_instruction
    if rule.execution == "unsupported":
        return rule.compilation_error
    if not rule.checks:
        return None
    detail = " ET ".join(_describe_check(check) for check in rule.checks)
    if rule.only_if is not None:
        state = "presente" if rule.only_if.state == "present" else "absente"
        detail += f" (si {rule.only_if.field} {state})"
    return detail