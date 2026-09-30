"""Tests de normalisation du guide metier S1000D."""

from __future__ import annotations

from pathlib import Path

from app.core.s1000d_guide import load_guide


GUIDE_PATH = Path(__file__).resolve().parents[2] / "Balise_S1000D.xlsx"


def test_guide_keeps_profiles_and_normalizes_composite_rows() -> None:
    guide = load_guide(GUIDE_PATH)

    assert guide.version == 1
    assert len(guide.rules_for("descriptive")) == 18
    assert len(guide.rules_for("procedural")) == 54

    warning = next(rule for rule in guide.rules_for("descriptive") if rule.element == "warning")
    assert warning.components == ("warning", "warningAndCautionPara")
    assert warning.business_role == "admonition"
    assert warning.example_text == "Risque d'électrocution."
    assert warning.optional_attributes == ("id",)
    assert warning.allowed_parents is None
    assert warning.allowed_children is None

    emphasis_rules = [rule for rule in guide.rules_for("descriptive") if rule.element == "emphasis"]
    assert {rule.variants[0] for rule in emphasis_rules} == {"em01", "em02"}

    dm_ref = next(rule for rule in guide.rules_for("descriptive") if rule.element == "dmRef")
    assert dm_ref.components == ("dmRef", "dmRefIdent", "dmCode")
    assert "modelIdentCode" in dm_ref.required_attributes


def test_guide_reports_gaps_without_rewriting_source_rows() -> None:
    guide = load_guide(GUIDE_PATH)
    issue_codes = {issue.code for issue in guide.issues}

    assert "STRUCTURE_NOT_SPECIFIED" in issue_codes
    assert "MISSING_DESCRIPTION" in issue_codes
    assert "MISSING_EXAMPLE" in issue_codes
    assert "CONFLICTING_DUPLICATE_DEFINITION" in issue_codes

    names = [rule for rule in guide.rules_for("procedural") if rule.element == "name"]
    assert len(names) == 2
    assert len({rule.source_row for rule in names}) == 2


def test_guide_can_be_exported_as_json_data() -> None:
    data = load_guide(GUIDE_PATH).to_dict()

    assert data["version"] == 1
    assert data["source_name"] == "Balise_S1000D.xlsx"
    assert isinstance(data["rules"], list)
    assert isinstance(data["issues"], list)
    assert isinstance(data["rules"][0]["components"], list)