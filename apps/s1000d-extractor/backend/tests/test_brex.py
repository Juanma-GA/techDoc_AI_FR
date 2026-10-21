"""BREX : parse des regles + validation comme porte."""

from __future__ import annotations

from app.core.brex import parse_brex
from app.core.brex_validation import validate_brex


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


def test_default_flag_is_optional_and_flag_one_requires_a_match() -> None:
    brex = (
        "<dmodule><content><brex><contextRules><structureObjectRuleGroup>"
        '<structureObjectRule id="required"><objectPath allowedObjectFlag="1">'
        "//para</objectPath><objectUse>Une para est obligatoire.</objectUse>"
        "</structureObjectRule>"
        "<structureObjectRule><objectPath>//note</objectPath></structureObjectRule>"
        "</structureObjectRuleGroup></contextRules></brex></content></dmodule>"
    )
    rules = parse_brex(brex)
    assert [rule.allowed_flag for rule in rules] == ["1", "2"]
    violations = validate_brex("<dmodule><content/></dmodule>", rules)
    assert any(v["rule"] == "BREX" and "obligatoire" in v["message"] for v in violations)


def test_closed_single_object_value_is_enforced() -> None:
    brex = (
        "<dmodule><content><brex><contextRules><structureObjectRuleGroup>"
        '<structureObjectRule id="value"><objectPath allowedObjectFlag="2">'
        "//item/@kind</objectPath><objectValue valueAllowed=\"approved\"/>"
        "</structureObjectRule>"
        "</structureObjectRuleGroup></contextRules></brex></content></dmodule>"
    )
    rules = parse_brex(brex)
    violations = validate_brex(
        '<dmodule><content><item kind="unapproved"/></content></dmodule>',
        rules,
    )
    assert any(v["rule"] == "BREX_VALUE" and v["brex_rule_id"] == "value" for v in violations)


def test_unsupported_object_value_form_is_reported() -> None:
    brex = (
        "<dmodule><content><brex><contextRules><structureObjectRuleGroup>"
        '<structureObjectRule><objectPath>//item/@kind</objectPath>'
        '<objectValue valueForm="range" valueAllowed="[A-Z]+"/>'
        "</structureObjectRule>"
        "</structureObjectRuleGroup></contextRules></brex></content></dmodule>"
    )
    violations = validate_brex(
        '<dmodule><content><item kind="invalid"/></content></dmodule>',
        parse_brex(brex),
    )
    assert any(v["rule"] == "BREX_VALUE_UNSUPPORTED" for v in violations)


def test_rule_support_status_distinguishes_context_and_unsupported_forms() -> None:
    brex = (
        "<dmodule><content><brex>"
        "<contextRules><structureObjectRuleGroup>"
        '<structureObjectRule><objectPath allowedObjectFlag="0">//emphasis</objectPath>'
        "</structureObjectRule>"
        '<structureObjectRule><objectPath allowedObjectFlag="0">//*['
        "</objectPath></structureObjectRule>"
        '<structureObjectRule><objectPath allowedObjectFlag="2">//item/@type</objectPath>'
        '<objectValue valueForm="range" valueAllowed="1-3"/>'
        "</structureObjectRule>"
        "</structureObjectRuleGroup></contextRules>"
        '<contextRules rulesContext="http://example.test/proced.xsd">'
        "<structureObjectRuleGroup><structureObjectRule>"
        '<objectPath allowedObjectFlag="0">//emphasis</objectPath>'
        "</structureObjectRule></structureObjectRuleGroup></contextRules>"
        "</brex></content></dmodule>"
    )
    rules = parse_brex(brex)

    assert [rule.support_status for rule in rules] == [
        "automatic", "unsupported", "unsupported", "contextual",
    ]
    assert [rule.support_reason for rule in rules] == [
        None, "invalid_object_path", "unsupported_value_form", None,
    ]


def test_context_rules_match_the_target_dm_schema_uri() -> None:
    schema_uri = "http://www.s1000d.org/S1000D_4-2/xml_schema_flat/descript.xsd"
    brex = (
        "<dmodule><content><brex><contextRules "
        f'rulesContext="{schema_uri}">'
        "<structureObjectRuleGroup><structureObjectRule>"
        '<objectPath allowedObjectFlag="0">//emphasis</objectPath>'
        "</structureObjectRule></structureObjectRuleGroup>"
        "</contextRules></brex></content></dmodule>"
    )
    rules = parse_brex(brex)
    other_schema = (
        '<dmodule xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:noNamespaceSchemaLocation="http://www.s1000d.org/S1000D_4-2/'
        'xml_schema_flat/proced.xsd"><content><emphasis>x</emphasis></content></dmodule>'
    )
    matching_schema = (
        '<dmodule xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xsi:noNamespaceSchemaLocation="{schema_uri}">'
        "<content><emphasis>x</emphasis></content></dmodule>"
    )
    assert validate_brex(other_schema, rules) == []
    assert any(v["rule"] == "BREX" for v in validate_brex(matching_schema, rules))


def test_context_rule_without_target_schema_is_unverifiable() -> None:
    brex = (
        "<dmodule><content><brex><contextRules rulesContext=\"unknown:context\">"
        "<structureObjectRuleGroup><structureObjectRule>"
        '<objectPath allowedObjectFlag="0">//emphasis</objectPath>'
        "</structureObjectRule></structureObjectRuleGroup>"
        "</contextRules></brex></content></dmodule>"
    )
    violations = validate_brex(
        "<dmodule><content><emphasis>x</emphasis></content></dmodule>",
        parse_brex(brex),
    )
    assert any(v["rule"] == "BREX_CONTEXT_UNVERIFIABLE" for v in violations)
