from __future__ import annotations

import fitz
import pytest

from app.core.compiled_rule_operators import (
    pressure_conversion_issues,
    unit_conversion_issues,
)
from app.core.compiled_rule_runtime import page_span_ranges
from app.parsers.pdf_parser import ParsedPage, Span, parse_pdf


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


def test_metric_conversion_rules_skip_list_of_materials_pages() -> None:
    text = "LIST OF MATERIALS\nSpacer, 25.4 mm\nWasher, 2.54 cm"

    assert unit_conversion_issues(text, "metric_length_to_inch") == []


@pytest.mark.parametrize(
    ("policy", "measurements"),
    [
        ("bar_to_psi", ["0.7 bar", "0.8 bar", "0.9 bar"]),
        ("pascal_to_inhg", ["10 kPa", "20 kPa", "30 kPa"]),
        ("metric_length_to_inch", ["2.5 mm", "4 mm", "6 mm"]),
        ("metric_mass_to_lb", ["2 kg", "4 kg", "6 kg"]),
        ("metric_torque_to_lbf_in", ["1 N.m", "2 N.m", "3 N.m"]),
    ],
)
def test_all_conversion_policies_skip_values_in_geometric_table_rows(
    policy: str,
    measurements: list[str],
) -> None:
    lines: list[str] = []
    spans: list[Span] = []
    for row_index, measurement in enumerate(measurements):
        y = 100.0 + row_index * 20.0
        cells = (str(row_index + 1), f"20000{row_index + 1}", measurement)
        lines.append(" ".join(cells))
        for cell, x0, x1 in zip(
            cells,
            (40.0, 80.0, 160.0),
            (48.0, 125.0, 320.0),
            strict=True,
        ):
            spans.append(
                Span(
                    text=cell,
                    bbox=(x0, y, x1, y + 12.0),
                    page=1,
                    font="Arial",
                    size=10.0,
                )
            )
    text = "\n".join(lines)
    page = ParsedPage(page=1, text=text, spans=spans, page_height=792.0)
    span_ranges = page_span_ranges(page)

    issues = (
        pressure_conversion_issues(text, span_ranges=span_ranges)
        if policy == "bar_to_psi"
        else unit_conversion_issues(text, policy, span_ranges=span_ranges)
    )

    assert issues == []


def test_metric_length_ranges_accept_and_correct_paired_conversions() -> None:
    valid = "Length: 25.4 mm and 50.8 mm (1.00 in. and 2.00 in.)"
    invalid = "Length: 25.4 mm and 50.8 mm (1.10 in. and 2.00 in.)"

    assert unit_conversion_issues(valid, "metric_length_to_inch") == []
    issues = unit_conversion_issues(invalid, "metric_length_to_inch")

    assert len(issues) == 1
    assert issues[0].original == "25.4 mm and 50.8 mm (1.10 in. and 2.00 in.)"
    assert issues[0].proposed == "25.4 mm and 50.8 mm (1.00 in. and 2.00 in.)"


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


@pytest.mark.parametrize(
    "content",
    [
        "400 g + 3% (0,882 lb + 3%)",
        "Torque the nut. Mass: 400 g + 3% (0,882 lb + 3%).",
    ],
)
def test_mass_conversion_pair_from_pdf_is_not_reported(tmp_path, content: str) -> None:
    # Synthetic stand-in for the client manual page (never commit client documents).
    pdf_path = tmp_path / "mass-pair.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), content, fontname="helv", fontsize=10)
    doc.save(str(pdf_path))
    doc.close()
    parsed = parse_pdf(pdf_path)
    page = next(page for page in parsed.pages if "400 g + 3%" in page.text)
    start = page.text.index("400 g + 3%")
    end = page.text.index(")", start) + 1
    extracted_example = page.text[start:end]

    assert extracted_example == "400 g + 3% (0,882 lb + 3%)"
    assert unit_conversion_issues(extracted_example, "metric_mass_to_lb") == []