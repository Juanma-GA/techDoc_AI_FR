"""BREX : parse des regles + validation comme porte."""

from __future__ import annotations

from app.core.brex import parse_brex, validate_brex


def test_parse_extracts_rule(brex_xml: str) -> None:
    rules = parse_brex(brex_xml)
    assert len(rules) == 1
    assert rules[0].allowed_flag == "0"
    assert rules[0].object_path == "//emphasis"


def test_forbidden_element_present_triggers_violation(brex_xml: str) -> None:
    rules = parse_brex(brex_xml)
    xml = "<dmodule><content><emphasis>x</emphasis></content></dmodule>"
    violations = validate_brex(xml, rules)
    assert any(v["rule"] == "BREX" and v["severity"] == "error" for v in violations)


def test_clean_document_no_violation(brex_xml: str) -> None:
    rules = parse_brex(brex_xml)
    xml = "<dmodule><content><para>ok</para></content></dmodule>"
    assert validate_brex(xml, rules) == []
