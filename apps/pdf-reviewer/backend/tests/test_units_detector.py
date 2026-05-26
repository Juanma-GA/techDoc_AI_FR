"""Unit detector — regex coverage and conversions."""

from __future__ import annotations

from app.core.units_detector import detect


def test_detects_cm_when_imperial_target() -> None:
    matches = detect("Torque value 12 cm and ignore.", target_system="imperial")
    assert any(m.unit == "cm" and "in" in m.proposed for m in matches)


def test_handles_french_decimal_comma() -> None:
    matches = detect("Diamètre 12,5 cm sur la page.", target_system="imperial")
    cm = [m for m in matches if m.unit == "cm"]
    assert cm and cm[0].value == 12.5


def test_inch_with_double_quote() -> None:
    matches = detect("Use a 5\" wrench.", target_system="metric")
    inches = [m for m in matches if m.unit == "in"]
    assert inches
    assert "cm" in inches[0].proposed


def test_feet_with_apostrophe() -> None:
    matches = detect("Width 2' total.", target_system="metric")
    feet = [m for m in matches if m.unit == "ft"]
    assert feet
    assert "m" in feet[0].proposed


def test_kg_to_lb() -> None:
    matches = detect("Mass 3 kg net.", target_system="imperial")
    kg = [m for m in matches if m.unit == "kg"]
    assert kg
    assert "lb" in kg[0].proposed


def test_lbs_to_kg() -> None:
    matches = detect("Mass 5 lbs net.", target_system="metric")
    lbs = [m for m in matches if m.unit == "lb"]
    assert lbs
    assert "kg" in lbs[0].proposed


def test_auto_target_picks_majority() -> None:
    text = "12 cm, 4 cm, 2 cm and one 5 in figure."
    matches = detect(text, target_system="auto")
    # Majority is metric, so imperial should be flagged.
    assert all(m.target_system == "metric" for m in matches)


def test_no_match_when_already_in_target() -> None:
    matches = detect("12 cm width", target_system="metric")
    assert matches == []
