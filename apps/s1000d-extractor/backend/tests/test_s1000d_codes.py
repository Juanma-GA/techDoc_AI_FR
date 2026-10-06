"""Tests du registre normalise des codes S1000D."""

from app.core.s1000d_codes import codes_for, emphasis_code_for_style, get_code, load_codes


def test_code_registry_contains_the_supplied_code_sets() -> None:
    registry = load_codes()
    names = {code_set.name for code_set in registry.code_sets}

    assert names == {
        "thresholdUnitOfMeasure",
        "skillLevelCode",
        "emphasisType",
        "internalRefTargetType",
        "quantityType",
    }
    assert registry.standard == "S1000D Issue 4.1"


def test_code_registry_expands_project_ranges_and_supports_lookup() -> None:
    assert get_code("thresholdUnitOfMeasure", "th01").label == "Flight hours"
    assert get_code("skillLevelCode", "sk99").status == "project"
    assert get_code("quantityType", "qty50") is None
    assert len(codes_for("emphasisType")) == 54


def test_code_registry_exposes_emphasis_style_mapping() -> None:
    assert emphasis_code_for_style("bold") == "em01"
    assert emphasis_code_for_style("italic") == "em02"
    assert get_code("emphasisType", "em05").notes == "Not to be used to mark deleted text"
    assert emphasis_code_for_style("unknown") is None