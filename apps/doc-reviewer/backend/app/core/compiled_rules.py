"""Strict contracts for deterministic compiled rules and their results."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


NormalizationStep = Literal["unicode", "trim", "spaces", "line_breaks"]


class RuleTarget(StrictModel):
    page: str
    region: Literal["full_page", "header", "body", "footer"]


class Check(StrictModel):
    field: Literal[
        "text",
        "page_number",
        "revision_number",
        "revision_date",
        "first_issue_date",
        "copyright_start_year",
        "copyright_end_year",
        "document_type",
    ]
    operator: Literal["exists", "not_exists", "equals", "regex", "normalized_equals"]
    expected: str | int | None = None
    normalization: list[NormalizationStep] | None = None

    @model_validator(mode="after")
    def validate_normalization(self) -> Check:
        if self.operator == "normalized_equals" and not self.normalization:
            raise ValueError("normalized_equals requires at least one normalization step")
        if self.operator != "normalized_equals" and self.normalization is not None:
            raise ValueError("normalization is only allowed with normalized_equals")
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
    severity: Literal["info", "warning", "error"] = "warning"
    execution: Literal["deterministic", "semantic", "manual", "unsupported"]
    target: RuleTarget
    checks: list[Check] = Field(default_factory=list)
    semantic_instruction: str | None = None
    manual_instruction: str | None = None
    compilation_error: str | None = None
    source: Literal["standard_rule", "user_checklist"]
    origin_ref: str | None = Field(default=None, max_length=500)

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