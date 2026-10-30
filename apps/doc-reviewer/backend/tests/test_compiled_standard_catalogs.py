"""Coverage for the built-in standards expressed as CompiledRule (catalog round trip and executor evidence)."""

from __future__ import annotations

from app.checks.standards import (
    BUILTIN_STANDARDS,
    serialize_builtin_version,
)
from app.core.compiled_rule_executor import execute_docx_rules
from app.core.standard_rule_compiler import compile_standard_rule
from app.parsers.docx_parser import Block
from tests.helpers.compiled_catalog import (
    _pdf,
    _rule,
    execute_pdf_rules,
)


def test_all_builtin_catalog_entries_round_trip_as_compiled_rules() -> None:
    total = 0
    for spec in BUILTIN_STANDARDS:
        metadata = spec["metadata"]
        for label in spec["versions"]:
            payloads = serialize_builtin_version(spec, label)
            total += len(payloads)
            assert all("id" in payload and "checks" in payload for payload in payloads)
            for payload in payloads:
                compiled = compile_standard_rule(payload, f"{spec['code']}:{label}")
                assert compiled is not None
                assert compiled.source == "standard_rule"
                assert metadata[compiled.id]["description_en"]
                assert metadata[compiled.id]["message"]
                assert metadata[compiled.id]["message_en"]
    assert total == 36


def test_mat_reference_format_is_passed_and_failed_by_the_compiled_executor() -> None:
    rule = _rule("MAT_REF_FORMAT")
    valid, _ = execute_pdf_rules(_pdf("See MAT-24-21-00-001."), [rule])
    invalid, _ = execute_pdf_rules(_pdf("See MAT-24-21-00."), [rule])
    assert valid[0].status == "PASS"
    assert invalid[0].status == "FAIL"


def test_conditional_periodicity_and_dual_torque_are_executed() -> None:
    periodicity = _rule("ATA_FIELD_PERIODICITE")
    missing, _ = execute_pdf_rules(_pdf("Preventive maintenance task."), [periodicity])
    present, _ = execute_pdf_rules(_pdf("Preventive maintenance task. Frequency: 200 FH."), [periodicity])
    assert missing[0].status == "FAIL"
    assert present[0].status == "PASS"

    torque = _rule("ATA_TORQUE_DUAL_UNIT")
    dual, _ = execute_pdf_rules(_pdf("Torque 12 N.m and 9 lb.ft."), [torque])
    single, _ = execute_pdf_rules(_pdf("Torque 12 N.m."), [torque])
    assert dual[0].status == "PASS"
    assert single[0].status == "FAIL"


def test_compiled_rules_produce_pdf_and_docx_evidence() -> None:
    rule = _rule("STE_NO_MAYBE")
    pdf_results, pdf_suggestions = execute_pdf_rules(_pdf("Maybe remove the panel."), [rule])
    docx_results, docx_suggestions = execute_docx_rules(
        [
            Block(
                target_id="dp1",
                index=1,
                zone="body",
                kind="paragraph",
                text="Maybe remove the panel.",
            )
        ],
        [rule],
    )
    assert pdf_results[0].status == "FAIL"
    assert pdf_results[0].evidence is not None
    assert pdf_suggestions[0].rule_code == "STE_NO_MAYBE"
    assert docx_results[0].status == "FAIL"
    assert docx_results[0].evidence is not None
    assert docx_suggestions[0].rule_code == "STE_NO_MAYBE"
