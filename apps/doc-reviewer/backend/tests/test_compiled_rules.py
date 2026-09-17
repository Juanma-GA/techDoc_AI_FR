"""Validation tests for CompiledRule and proof-bearing RuleResult."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.core.compiled_rules import (
    Check,
    CompiledRule,
    Condition,
    DocxEvidenceLocation,
    Evidence,
    FieldRef,
    PdfEvidenceLocation,
    PrimitiveStep,
    RuleExample,
    RulePrerequisite,
    RuleResult,
    RuleTarget,
    describe_compiled_rule,
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


def test_regex_checks_are_compiled_at_validation_time() -> None:
    Check(field="text", operator="regex", expected=r"\bTODO\b")
    Check(field="text", operator="regex_exists", expected=r"REV\s+\d+")

    with pytest.raises(ValidationError, match="regex invalide"):
        Check(field="text", operator="regex_exists", expected="[")


def test_font_size_operator_requires_a_positive_numeric_expected_value() -> None:
    Check(field="cmm_number", operator="font_size_equals", expected=23)
    Check(field="thales_logo_t", operator="font_size_equals", expected=31)
    Check(field="cmm_number", operator="font_size_equals", expected=23.0)

    with pytest.raises(ValidationError, match="numeric expected value"):
        Check(field="cmm_number", operator="font_size_equals", expected="23")
    with pytest.raises(ValidationError, match="positive expected value"):
        Check(field="cmm_number", operator="font_size_equals", expected=0)


def test_contains_operators_require_a_non_empty_list() -> None:
    Check(field="text", operator="contains_none", expected=["obsolete", "deprecated"])

    with pytest.raises(ValidationError, match="requires a non-empty list"):
        Check(field="text", operator="contains_none", expected="obsolete")
    with pytest.raises(ValidationError, match="requires a non-empty list"):
        Check(field="text", operator="contains_any", expected=[])
    with pytest.raises(ValidationError, match="does not accept a list"):
        Check(field="text", operator="exists", expected=["a", "b"])


def test_replacement_is_only_allowed_on_search_operators() -> None:
    Check(field="text", operator="not_exists", expected="obsolete", replacement="legacy")
    Check(field="text", operator="contains_none", expected=["a", "b"], replacements={"a": "x"})

    with pytest.raises(ValidationError, match="only allowed with regex, not_exists or contains_none"):
        Check(field="text", operator="exists", expected="a", replacement="b")
    with pytest.raises(ValidationError, match="only allowed with contains_none"):
        Check(field="text", operator="not_exists", expected="a", replacements={"a": "b"})
    with pytest.raises(ValidationError, match="either replacement or replacements"):
        Check(field="text", operator="contains_none", expected=["a"], replacement="x", replacements={"a": "y"})


def test_equals_field_requires_compare_to_and_no_literal_expected() -> None:
    Check(
        field="copyright_end_year",
        operator="equals_field",
        compare_to=FieldRef(source="document_meta", field="meta_revision_date", normalization=["extract_year"]),
    )

    with pytest.raises(ValidationError, match="equals_field requires compare_to"):
        Check(field="copyright_end_year", operator="equals_field")
    with pytest.raises(ValidationError, match="equals_field must not set expected"):
        Check(
            field="copyright_end_year",
            operator="equals_field",
            expected="2026",
            compare_to=FieldRef(source="document_meta", field="meta_revision_date"),
        )
    with pytest.raises(ValidationError, match="only allowed with equals_field"):
        Check(
            field="text",
            operator="exists",
            compare_to=FieldRef(source="document_meta", field="meta_revision_date"),
        )


def test_field_ref_validates_field_against_its_source() -> None:
    FieldRef(source="document_text", field="text")
    FieldRef(source="document_meta", field="meta_cmm_number")

    with pytest.raises(ValidationError, match="champ invalide"):
        FieldRef(source="document_meta", field="text")
    with pytest.raises(ValidationError, match="champ invalide"):
        FieldRef(source="document_text", field="meta_cmm_number")


def test_compiled_rule_validates_primitive_plan_and_examples() -> None:
    rule = CompiledRule(
        id="CHECKLIST_PRIMITIVE_PLAN",
        topic="Copyright",
        execution="deterministic",
        target=RuleTarget(page="all", region="footer"),
        checks=[Check(field="text", operator="exists", expected="Copyright")],
        primitive_plan=[
            PrimitiveStep(
                step_id="select-footer",
                primitive="select.target",
                parameters={"page": "all", "region": "footer"},
            ),
            PrimitiveStep(
                step_id="assert-mention",
                primitive="assert.exists",
                parameters={"expected": "Copyright"},
                input_from={"text": "select-footer"},
            ),
        ],
        hypotheses=["The footer contains a literal copyright mention."],
        valid_examples=[RuleExample(text="Copyright 2026 Example", outcome="valid")],
        invalid_examples=[RuleExample(text="No legal notice", outcome="invalid")],
        prerequisites=[
            RulePrerequisite(reference_id="document.document_language", reason="The rule is language-aware.")
        ],
        source="user_checklist",
    )

    assert rule.primitive_plan[0].primitive == "select.target"
    assert rule.valid_examples[0].outcome == "valid"


def test_compiled_rule_rejects_unknown_primitive() -> None:
    with pytest.raises(ValidationError, match=r"primitive\(s\) inconnue\(s\)"):
        CompiledRule(
            id="CHECKLIST_UNKNOWN_PRIMITIVE",
            topic="Unknown",
            execution="deterministic",
            target=RuleTarget(page="all", region="full_page"),
            checks=[Check(field="text", operator="exists", expected="x")],
            primitive_plan=[PrimitiveStep(step_id="unknown", primitive="does.not_exist")],
            source="user_checklist",
        )


def test_compiled_rule_rejects_unknown_primitive_reference() -> None:
    with pytest.raises(ValidationError, match=r"reference\(s\) inconnue\(s\)"):
        CompiledRule(
            id="CHECKLIST_UNKNOWN_REFERENCE",
            topic="Unknown",
            execution="deterministic",
            target=RuleTarget(page="all", region="full_page"),
            checks=[Check(field="text", operator="exists", expected="x")],
            primitive_plan=[
                PrimitiveStep(
                    step_id="reference",
                    primitive="reference.document",
                    parameters={"reference_id": "document.unknown"},
                )
            ],
            source="user_checklist",
        )


def test_only_if_condition_gates_a_compiled_rule() -> None:
    rule = CompiledRule(
        id="CHECKLIST_CMM",
        topic="CMM footer",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[Check(field="text", operator="exists", expected="CMM")],
        source="user_checklist",
        only_if=Condition(field="meta_cmm_number", state="present"),
    )
    assert rule.only_if == Condition(field="meta_cmm_number", state="present")


def test_describe_compiled_rule_summarizes_deterministic_checks() -> None:
    rule = CompiledRule(
        id="CHECKLIST_TERMS",
        topic="Checklist",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[
            Check(
                field="text",
                operator="contains_none",
                expected=["obsolete", "deprecated"],
                replacements={"obsolete": "legacy"},
            )
        ],
        source="user_checklist",
        only_if=Condition(field="meta_cmm_number", state="present"),
    )
    detail = describe_compiled_rule(rule)
    assert detail is not None
    assert "obsolete" in detail and "deprecated" in detail
    assert "remplacement propose" in detail
    assert "meta_cmm_number" in detail


def test_describe_compiled_rule_falls_back_to_instruction_or_error() -> None:
    semantic = CompiledRule(
        id="CHECKLIST_SEM",
        topic="Style",
        execution="semantic",
        target=RuleTarget(page="all", region="full_page"),
        semantic_instruction="Verify the tone is neutral.",
        source="user_checklist",
    )
    assert describe_compiled_rule(semantic) == "Verify the tone is neutral."

    unsupported = CompiledRule(
        id="CHECKLIST_UNSUP",
        topic="Table",
        execution="unsupported",
        target=RuleTarget(page="all", region="full_page"),
        compilation_error="operator contains is not supported",
        source="user_checklist",
    )
    assert describe_compiled_rule(unsupported) == "operator contains is not supported"


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


def test_checklist_compiler_normalizes_catalog_style_primitive_steps() -> None:
    def chat(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "id": checklist_rule_id("checklist.xlsx:Review:7"),
                "topic": "Revision",
                "execution": "deterministic",
                "target": {"page": "all", "region": "header"},
                "checks": [{"field": "revision_number", "operator": "exists", "expected": "REV 01"}],
                "primitive_plan": [
                    {"id": "select.target", "parameters": {"page": "all", "region": "header"}},
                    {
                        "id": "reference.document",
                        "parameters": {"reference_id": "document.meta_revision_number"},
                    },
                ],
                "source": "user_checklist",
                "origin_ref": "checklist.xlsx:Review:7",
            }
        )

    rule = compile_checklist_rule(SessionLocal(), _checklist_row(), "checklist.xlsx", chat=chat)

    assert rule.execution == "deterministic"
    assert [step.step_id for step in rule.primitive_plan] == ["step_1", "step_2"]
    assert [step.primitive for step in rule.primitive_plan] == [
        "select.target",
        "reference.document",
    ]


def test_checklist_compiler_forces_target_over_a_drifting_llm_echo() -> None:
    """The LLM sometimes echoes back a wrong `target` (e.g. page="1" instead
    of "all") — the row's own zone column is authoritative, so a drifting
    echo must not make the whole rule unsupported."""

    def chat(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "id": checklist_rule_id("checklist.xlsx:Review:7"),
                "topic": "Copyright",
                "execution": "deterministic",
                "target": {"page": "1", "region": "footer"},
                "checks": [{"field": "text", "operator": "exists", "expected": "Copyright"}],
                "source": "user_checklist",
                "origin_ref": "checklist.xlsx:Review:7",
            }
        )

    rule = compile_checklist_rule(
        SessionLocal(), _checklist_row(target_zone="footer"), "checklist.xlsx", chat=chat
    )
    assert rule.execution == "deterministic"
    assert rule.target.page == "all"
    assert rule.target.region == "footer"


def test_checklist_compiler_drops_invalid_only_if_field() -> None:
    """A `only_if.field` outside the document_meta vocabulary (e.g. a
    Check.field value like document_type) must not crash the whole rule."""

    def chat(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "id": checklist_rule_id("checklist.xlsx:Review:7"),
                "topic": "Copyright",
                "execution": "deterministic",
                "target": {"page": "all", "region": "footer"},
                "checks": [{"field": "text", "operator": "exists", "expected": "Copyright"}],
                "only_if": {"field": "document_type", "state": "present"},
                "source": "user_checklist",
                "origin_ref": "checklist.xlsx:Review:7",
            }
        )

    rule = compile_checklist_rule(
        SessionLocal(), _checklist_row(target_zone="footer"), "checklist.xlsx", chat=chat
    )
    assert rule.execution == "deterministic"
    assert rule.only_if is None


def test_checklist_compiler_sends_reference_catalog_without_document_values() -> None:
    captured: dict[str, object] = {}

    def chat(_db, system_prompt: str, user_prompt: str, **_kwargs) -> str:
        captured["system"] = system_prompt
        captured["user"] = json.loads(user_prompt)
        return json.dumps(
            {
                "id": checklist_rule_id("checklist.xlsx:Review:7"),
                "topic": "Revision",
                "execution": "deterministic",
                "target": {"page": "all", "region": "header"},
                "checks": [{"field": "revision_number", "operator": "equals", "expected": "REV 02"}],
                "source": "user_checklist",
                "origin_ref": "checklist.xlsx:Review:7",
            }
        )

    rule = compile_checklist_rule(SessionLocal(), _checklist_row(), "checklist.xlsx", chat=chat)

    assert rule.execution == "deterministic"
    prompt = captured["user"]
    assert isinstance(prompt, dict)
    assert prompt["primitive_catalog"]["version"] == "1.0"
    assert any(
        item["id"] == "document.meta_revision_date"
        for item in prompt["primitive_catalog"]["references"]
    )
    assert any(
        item["id"] == "assert.equals_reference"
        for item in prompt["primitive_catalog"]["primitives"]
    )
    assert "MAR 18/26" not in str(prompt)
    assert "32-11-00" not in str(prompt)
    assert "settings_context" not in str(captured["system"])


def test_checklist_compiler_accepts_wrapped_deterministic_output() -> None:
    origin_ref = "checklist.xlsx:Review:7"

    def chat(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "required_metadata": {
                    "id": checklist_rule_id(origin_ref),
                    "topic": "Revision",
                    "source": "user_checklist",
                    "origin_ref": origin_ref,
                },
                "target": {"page": "all", "region": "header"},
                "rules": [
                    {"field": "revision_number", "operator": "equals", "expected": "REV 02"}
                ],
            }
        )

    rule = compile_checklist_rule(SessionLocal(), _checklist_row(), "checklist.xlsx", chat=chat)

    assert rule.execution == "deterministic"
    assert rule.checks[0].field == "revision_number"


def test_checklist_compiler_normalizes_value_alias() -> None:
    def chat(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "id": checklist_rule_id("checklist.xlsx:Review:7"),
                "topic": "Revision",
                "execution": "deterministic",
                "target": {"page": "all", "region": "header"},
                "checks": [{"field": "revision_date", "operator": "regex", "value": r"JAN\s+\d{2}"}],
                "source": "user_checklist",
                "origin_ref": "checklist.xlsx:Review:7",
            }
        )

    rule = compile_checklist_rule(SessionLocal(), _checklist_row(), "checklist.xlsx", chat=chat)

    assert rule.execution == "deterministic"
    assert rule.checks[0].expected == r"JAN\s+\d{2}"


def test_checklist_compiler_promotes_embedded_semantic_instruction() -> None:
    def chat(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "id": checklist_rule_id("checklist.xlsx:Review:7"),
                "topic": "Revision",
                "execution": "deterministic",
                "target": {"page": "all", "region": "header"},
                "checks": [
                    {"field": "revision_number", "operator": "equals", "expected": "REV 02"},
                    {"semantic_instruction": "Vérifier que le numéro respecte la présentation attendue."},
                ],
                "source": "user_checklist",
                "origin_ref": "checklist.xlsx:Review:7",
            }
        )

    rule = compile_checklist_rule(SessionLocal(), _checklist_row(), "checklist.xlsx", chat=chat)

    assert rule.execution == "semantic"
    assert rule.checks == []
    assert "présentation attendue" in (rule.semantic_instruction or "")
    assert "revision_number" in (rule.semantic_instruction or "")


def test_checklist_compiler_promotes_root_semantic_instruction_with_checks() -> None:
    def chat(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "id": checklist_rule_id("checklist.xlsx:Review:7"),
                "topic": "Revision",
                "execution": "semantic",
                "target": {"page": "all", "region": "footer"},
                "checks": [
                    {"field": "revision_date", "operator": "regex", "expected": r"MAR\s+\d{2}/\d{2}"}
                ],
                "semantic_instruction": "Vérifier que la date de révision correspond à la date attendue.",
                "source": "user_checklist",
                "origin_ref": "checklist.xlsx:Review:7",
            }
        )

    rule = compile_checklist_rule(
        SessionLocal(),
        _checklist_row(target_zone="footer"),
        "checklist.xlsx",
        chat=chat,
    )

    assert rule.execution == "semantic"
    assert rule.checks == []
    assert "date de révision" in (rule.semantic_instruction or "")
    assert "revision_date" in (rule.semantic_instruction or "")


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