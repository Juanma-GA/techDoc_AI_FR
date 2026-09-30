from __future__ import annotations

from pathlib import Path

import pytest

from app.core.compiled_rule_operators import (
    pressure_conversion_issues,
    unit_conversion_issues,
)
from app.parsers.pdf_parser import parse_pdf


@pytest.mark.parametrize(
    ("policy", "text"),
    [
        ("pascal_to_inhg", "101.325 kPa +- 3% (29.92 inHg + 3%)"),
        ("metric_length_to_inch", "2.54 cm +- 3% (1.00 in. + 3%)"),
        ("pascal_to_inhg", "Pressure: 101325 Pa (29.92 inHg)"),
        ("pascal_to_inhg", "Pressure: 1013.25 hPa (29.92 in.Hg)"),
        ("pascal_to_inhg", "Pressure: 101.325 kPa (29.92 in Hg)"),
        ("pascal_to_inhg", "Pressure: 0.101325 MPa (29.92 inHg)"),
        ("metric_length_to_inch", "Length: 25.4 mm (1.00 in.)"),
        ("metric_length_to_inch", "Length: 2.54 cm (1 inch)"),
        ("metric_length_to_inch", "Length: 0.0254 m (1.00 inches)"),
        ("metric_length_to_inch", "Length: 0.0000254 km (1.00 in.)"),
        ("pascal_to_inhg", "101.325 kPa +- 3% (29.92 inHg + 3%)"),
        ("metric_length_to_inch", "2.54 cm +- 3% (1.00 in. + 3%)"),
        ("metric_mass_to_lb", "Mass: 1 kg (2.20 lb)"),
        ("metric_mass_to_lb", "Mass: 1 g (0.00220 lb)"),
        ("metric_mass_to_lb", "Mass: 1 mg (0.00000220 lb)"),
        ("metric_mass_to_lb", "400 g +- 3% (0.882 lb +- 3%)"),
        ("metric_mass_to_lb", "400 g + 3% (0,882 lb + 3%)"),
        ("metric_mass_to_lb", "400 g \u00b1 3% (0.882 lb \u00b1 3%)"),
        ("metric_mass_to_lb", "400 g +/- 3% (0.882 lb +/- 3%)"),
        ("metric_torque_to_lbf_in", "1 daN.m +- 3% (88.51 lbf.in + 3%)"),
        ("metric_torque_to_lbf_in", "1 daN.m +- 3% (88.51 lbf.in + 3%)"),
        ("metric_torque_to_lbf_in", "Torque: 1 N.m (8.85 lbf.in)"),
        ("metric_torque_to_lbf_in", "Torque: 1 daN.m (88.51 lbf·in)"),
        ("metric_torque_to_lbf_in", "Torque: 1 kN.m (8850.75 lbf.in)"),
    ],
)
def test_valid_siemens_and_imperial_conversions_pass(policy: str, text: str) -> None:
    assert unit_conversion_issues(text, policy) == []


@pytest.mark.parametrize(
    ("policy", "text", "expected_proposal"),
    [
        (
            "pascal_to_inhg",
            "Pressure: 101325 Pa",
            "101325 Pa (29.92 inHg)",
        ),
        (
            "pascal_to_inhg",
            "Pressure: 101325 Pa (29.50 psi)",
            "101325 Pa (29.92 inHg)",
        ),
        (
            "metric_length_to_inch",
            "Length: 25.4 mm",
            "25.4 mm (1.00 in.)",
        ),
        (
            "metric_length_to_inch",
            "Length: 25.4 mm (1.20 cm)",
            "25.4 mm (1.00 in.)",
        ),
        (
            "metric_mass_to_lb",
            "Mass: 1 kg",
            "1 kg (2.20 lb)",
        ),
        (
            "metric_mass_to_lb",
            "Mass: 500 g (1.50 lb)",
            "500 g (1.10 lb)",
        ),
        (
            "metric_mass_to_lb",
            "400 g +- 3%",
            "400 g +- 3% (0.882 lb +- 3%)",
        ),
        (
            "metric_mass_to_lb",
            "400 g +- 3% (0.882 lb + 2%)",
            "400 g +- 3% (0.882 lb +- 3%)",
        ),
        (
            "pascal_to_inhg",
            "101.325 kPa + 3% (29.92 inHg + 2%)",
            "101.325 kPa + 3% (29.92 inHg + 3%)",
        ),
        (
            "metric_length_to_inch",
            "2.54 cm + 3% (1.00 in. + 2%)",
            "2.54 cm + 3% (1.00 in. + 3%)",
        ),
        (
            "metric_torque_to_lbf_in",
            "1 daN.m + 3% (88.51 lbf.in + 2%)",
            "1 daN.m + 3% (88.51 lbf.in + 3%)",
        ),
        (
            "metric_torque_to_lbf_in",
            "Torque: 1 daN.m",
            "1 daN.m (88.51 lbf.in)",
        ),
        (
            "metric_torque_to_lbf_in",
            "Torque: 1 daN.m (88.51 lbf)",
            "1 daN.m (88.51 lbf.in)",
        ),
    ],
)
def test_missing_or_invalid_conversions_propose_the_expected_pair(
    policy: str,
    text: str,
    expected_proposal: str,
) -> None:
    issues = unit_conversion_issues(text, policy)

    assert len(issues) == 1
    assert issues[0].proposed == expected_proposal


def test_unknown_unit_conversion_policy_has_no_findings() -> None:
    assert unit_conversion_issues("Pressure: 101325 Pa", "unknown_policy") == []


@pytest.mark.parametrize(
    "text",
    [
        "0.7 bar +- 3% (10.15 p.s.i. + 3%)",
        "0.7 bar + 3% (10.15 psi +- 3%)",
    ],
)
def test_bar_psi_accepts_matching_pdf_degraded_uncertainty(text: str) -> None:
    assert pressure_conversion_issues(text) == []


@pytest.mark.parametrize(
    ("policy", "text", "expected_proposal"),
    [
        (
            "bar_to_psi",
            "0.7 bar + 3% (10.15 psi + 2%)",
            "0.7 bar + 3% (10.15 p.s.i. + 3%)",
        ),
        (
            "pascal_to_inhg",
            "101.325 kPa + 3% (29.92 inHg + 2%)",
            "101.325 kPa + 3% (29.92 inHg + 3%)",
        ),
        (
            "metric_length_to_inch",
            "2.54 cm + 3% (1.00 in. + 2%)",
            "2.54 cm + 3% (1.00 in. + 3%)",
        ),
        (
            "metric_mass_to_lb",
            "400 g + 3% (0.882 lb + 2%)",
            "400 g + 3% (0.882 lb + 3%)",
        ),
        (
            "metric_torque_to_lbf_in",
            "1 daN.m + 3% (88.51 lbf.in + 2%)",
            "1 daN.m + 3% (88.51 lbf.in + 3%)",
        ),
    ],
)
def test_mismatched_uncertainty_is_reported_for_every_conversion_policy(
    policy: str,
    text: str,
    expected_proposal: str,
) -> None:
    issues = (
        pressure_conversion_issues(text)
        if policy == "bar_to_psi"
        else unit_conversion_issues(text, policy)
    )

    assert len(issues) == 1
    assert issues[0].proposed == expected_proposal


def test_mass_conversion_pair_from_example_pdf_is_not_reported() -> None:
    pdf_path = Path(__file__).resolve().parents[2] / "79-30-02-01_test_erreur.pdf"
    parsed = parse_pdf(pdf_path)
    page = next(page for page in parsed.pages if "400 g + 3%" in page.text)
    start = page.text.index("400 g + 3%")
    end = page.text.index(")", start) + 1
    extracted_example = page.text[start:end]

    assert extracted_example == "400 g + 3% (0,882 lb + 3%)"
    assert unit_conversion_issues(extracted_example, "metric_mass_to_lb") == []