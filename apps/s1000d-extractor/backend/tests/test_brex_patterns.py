from __future__ import annotations

from app.core.brex import parse_brex
from app.core.brex_validation import validate_brex


def _pattern_brex() -> str:
    return (
        "<dmodule><content><brex><contextRules><structureObjectRuleGroup>"
        '<structureObjectRule id="icn-format">'
        '<objectPath allowedObjectFlag="2">//@infoEntityRefIdent</objectPath>'
        '<objectValue valueForm="pattern" '
        'valueAllowed="(ICN-[A-Z0-9]{5}-[A-Z0-9]{5,10}-[0-9]{3}-[0-9]{2})"/>'
        "</structureObjectRule></structureObjectRuleGroup></contextRules>"
        "</brex></content></dmodule>"
    )


def test_closed_pattern_value_is_supported_and_checked_as_a_full_value() -> None:
    rules = parse_brex(_pattern_brex())
    assert rules[0].support_reason is None
    assert rules[0].support_status == "automatic"

    matching = (
        '<dmodule><content><graphic infoEntityRefIdent="ICN-ABCDE-FGHIJ-123-45"/>'
        "</content></dmodule>"
    )
    nonmatching = (
        '<dmodule><content><graphic infoEntityRefIdent="ICN-abcde-FGHIJ-123-45"/>'
        "</content></dmodule>"
    )

    assert validate_brex(matching, rules) == []
    violations = validate_brex(nonmatching, rules)
    assert any(
        violation["rule"] == "BREX_VALUE"
        and violation["brex_rule_id"] == "icn-format"
        for violation in violations
    )


def test_optional_pattern_value_does_not_require_an_attribute() -> None:
    assert validate_brex("<dmodule><content/></dmodule>", parse_brex(_pattern_brex())) == []


def test_invalid_pattern_is_reported_as_unverifiable() -> None:
    brex = _pattern_brex().replace(
        "(ICN-[A-Z0-9]{5}-[A-Z0-9]{5,10}-[0-9]{3}-[0-9]{2})",
        "[",
    )
    rules = parse_brex(brex)

    assert rules[0].support_reason == "invalid_value_pattern"
    violations = validate_brex(
        '<dmodule><content><graphic infoEntityRefIdent="ICN-ABCDE-FGHIJ-123-45"/>'
        "</content></dmodule>",
        rules,
    )
    assert any(violation["rule"] == "BREX_VALUE_UNSUPPORTED" for violation in violations)
