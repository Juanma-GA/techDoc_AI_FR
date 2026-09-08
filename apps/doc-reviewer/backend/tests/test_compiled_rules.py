"""Validation tests for CompiledRule and proof-bearing RuleResult."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.core.compiled_rules import (
    Check,
    CompiledRule,
    DocxEvidenceLocation,
    Evidence,
    PdfEvidenceLocation,
    RuleResult,
    RuleTarget,
    validate_compiled_rule_json,
)
from app.core.standard_rule_compiler import compile_standard_rule
from app.checks.standards.ata100 import CATALOG as ATA_CATALOG
from app.core.compiled_rule_store import persist_compiled_rule
from app.core.checklist_compiler import checklist_rule_id, compile_checklist_rule
from app.core.excel_rules import ParsedRule
from app.db.session import SessionLocal


def _compiled_rule() -> CompiledRule:
    return CompiledRule(
        id="CHECKLIST_TODO",
        topic="Editorial",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[Check(field="text", operator="regex", expected=r"\bTODO\b")],
        source="user_checklist",
        origin_ref="checklist.xlsx:Sheet1:2",
    )


def test_deterministic_rule_accepts_checks_and_round_trips() -> None:
    rule = _compiled_rule()
    assert validate_compiled_rule_json(rule.model_dump_json()) == rule


@pytest.mark.parametrize(
    "changes,expected_error",
    [
        ({"checks": []}, "at least one check"),
        ({"manual_instruction": "Inspect"}, "requires manual_instruction and compilation_error"),
        ({"compilation_error": "No operator"}, "requires manual_instruction and compilation_error"),
    ],
)
def test_deterministic_rule_rejects_invalid_shape(changes: dict, expected_error: str) -> None:
    payload = _compiled_rule().model_dump()
    payload.update(changes)
    with pytest.raises(ValidationError, match=expected_error):
        CompiledRule.model_validate(payload)


def test_manual_rule_requires_instruction_and_empty_checks() -> None:
    valid = CompiledRule(
        id="CHECKLIST_LOGO",
        topic="Branding",
        execution="manual",
        target=RuleTarget(page="all", region="full_page"),
        checks=[],
        manual_instruction="Verify the logo visually.",
        source="user_checklist",
    )
    assert valid.execution == "manual"

    with pytest.raises(ValidationError, match="manual_instruction"):
        CompiledRule.model_validate({**valid.model_dump(), "manual_instruction": None})
    with pytest.raises(ValidationError, match="empty checks"):
        CompiledRule.model_validate({**valid.model_dump(), "checks": [_compiled_rule().checks[0].model_dump()]})


def test_unsupported_rule_requires_error_and_empty_checks() -> None:
    valid = CompiledRule(
        id="CHECKLIST_TABLE",
        topic="Tables",
        execution="unsupported",
        target=RuleTarget(page="all", region="full_page"),
        checks=[],
        compilation_error="operator contains is not supported",
        source="user_checklist",
    )
    assert valid.execution == "unsupported"

    with pytest.raises(ValidationError, match="compilation_error"):
        CompiledRule.model_validate({**valid.model_dump(), "compilation_error": None})
    with pytest.raises(ValidationError, match="empty checks"):
        CompiledRule.model_validate({**valid.model_dump(), "checks": [_compiled_rule().checks[0].model_dump()]})


def test_normalized_equals_requires_normalization() -> None:
    valid = Check(
        field="revision_number",
        operator="normalized_equals",
        expected="REV 01",
        normalization=["unicode", "trim", "spaces"],
    )
    assert valid.normalization == ["unicode", "trim", "spaces"]

    with pytest.raises(ValidationError, match="requires at least one normalization step"):
        Check(field="revision_number", operator="normalized_equals", expected="REV 01")
    with pytest.raises(ValidationError, match="only allowed"):
        Check(field="text", operator="equals", expected="A", normalization=["trim"])


def test_rule_results_enforce_evidence_contract() -> None:
    pdf_evidence = Evidence(
        page="1",
        location=PdfEvidenceLocation(bbox=(10.0, 20.0, 30.0, 40.0)),
        observed_value="TODO",
        expected_value=r"\bTODO\b",
    )
    docx_evidence = Evidence(
        page="2",
        location=DocxEvidenceLocation(target_id="dp12"),
        observed_value="REV 01",
        expected_value="REV 02",
    )
    assert RuleResult(rule_id="R1", status="FAIL", evidence=pdf_evidence).status == "FAIL"
    assert RuleResult(rule_id="R2", status="PASS", evidence=docx_evidence).status == "PASS"

    for status in ("PASS", "FAIL", "INCONCLUSIVE"):
        with pytest.raises(ValidationError, match="requires evidence"):
            RuleResult(rule_id="R3", status=status)
    assert RuleResult(rule_id="R4", status="MANUAL").evidence is None
    assert RuleResult(rule_id="R5", status="UNSUPPORTED").evidence is None
    with pytest.raises(ValidationError, match="requires evidence to be None"):
        RuleResult(rule_id="R6", status="MANUAL", evidence=docx_evidence)


def test_compiled_rule_persistence_is_versioned_hashed_and_auto_activated() -> None:
    session = SessionLocal()
    try:
        row = persist_compiled_rule(session, _compiled_rule())

        assert row.code == "CHECKLIST_TODO"
        assert row.version == 1
        assert row.source_ref == "checklist.xlsx:Sheet1:2"
        assert row.active is True
        assert len(row.content_sha256) == 64
        assert validate_compiled_rule_json(row.compiled_json) == _compiled_rule()
    finally:
        session.rollback()
        session.close()


def test_ata_chapter_ref_is_corrected_and_migrated() -> None:
    source = next(rule for rule in ATA_CATALOG["rev 38"] if rule.code == "ATA_CHAPTER_REF")
    compiled = compile_standard_rule(source.as_dict(), "ATA100:rev 38:ATA_CHAPTER_REF")

    assert compiled is not None
    assert compiled.source == "standard_rule"
    assert compiled.checks == [Check(field="text", operator="regex", expected=source.pattern)]
    assert source.pattern is not None
    import re

    assert re.search(source.pattern, "See ATA 24-21-00") is None
    assert re.search(source.pattern, "See ATA 24.21.0") is not None


def test_ambiguous_regex_flag_is_not_migrated() -> None:
    source = next(rule for rule in ATA_CATALOG["rev 38"] if rule.code == "ATA_TORQUE_DUAL_UNIT")
    assert compile_standard_rule(source.as_dict(), "ATA100:rev 38:ATA_TORQUE_DUAL_UNIT") is None


def _checklist_row(**changes: str) -> ParsedRule:
    values = {
        "sheet": "Review",
        "row_number": 7,
        "check": "The revision number must equal REV 02.",
        "handling": "auto",
        "context": "Title block",
        "name": "The revision number must equal REV 02. | Title block",
        "category": "Revision",
        "kind": "llm_nl",
        "pattern": "",
        "replacement": "",
        "target_zone": "header",
        "severity": "warning",
        "message": "The revision number must equal REV 02. | Title block",
    }
    values.update(changes)
    return ParsedRule(**values)


def test_checklist_compiler_accepts_deterministic_output() -> None:
    def chat(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "id": checklist_rule_id("checklist.xlsx:Review:7"),
                "topic": "Revision",
                "execution": "deterministic",
                "target": {"page": "all", "region": "header"},
                "checks": [{"field": "revision_number", "operator": "equals", "expected": "REV 02"}],
                "manual_instruction": None,
                "compilation_error": None,
                "source": "user_checklist",
                "origin_ref": "checklist.xlsx:Review:7",
            }
        )

    rule = compile_checklist_rule(SessionLocal(), _checklist_row(), "checklist.xlsx", chat=chat)
    assert rule.execution == "deterministic"
    assert rule.target.region == "header"


def test_checklist_compiler_accepts_manual_output() -> None:
    row = _checklist_row(
        check="Verify the logo placement visually.",
        handling="manual",
        target_zone="",
    )

    def chat(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "id": checklist_rule_id("checklist.xlsx:Review:7"),
                "topic": "Revision",
                "execution": "manual",
                "target": {"page": "all", "region": "full_page"},
                "checks": [],
                "manual_instruction": "Verify the logo placement visually.",
                "compilation_error": None,
                "source": "user_checklist",
                "origin_ref": "checklist.xlsx:Review:7",
            }
        )

    rule = compile_checklist_rule(SessionLocal(), row, "checklist.xlsx", chat=chat)
    assert rule.execution == "manual"
    assert rule.manual_instruction is not None


def test_checklist_compiler_keeps_unsupported_output_visible() -> None:
    row = _checklist_row(check="The table must contain five rows.", target_zone="table")

    def chat(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "id": checklist_rule_id("checklist.xlsx:Review:7"),
                "topic": "Revision",
                "execution": "unsupported",
                "target": {"page": "all", "region": "full_page"},
                "checks": [],
                "manual_instruction": None,
                "compilation_error": "field table et operator count_equals non supportés",
                "source": "user_checklist",
                "origin_ref": "checklist.xlsx:Review:7",
            }
        )

    rule = compile_checklist_rule(SessionLocal(), row, "checklist.xlsx", chat=chat)
    assert rule.execution == "unsupported"
    assert "count_equals" in (rule.compilation_error or "")