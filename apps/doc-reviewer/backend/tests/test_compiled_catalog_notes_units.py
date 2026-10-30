"""Compiled catalog: note pages, unit conversions and wording rules."""

from __future__ import annotations

import pytest

from app.checks.thales_rules.ata100.page_classifier import (
    REPAIR_PAGE_TYPE,
    STORAGE_PAGE_TYPE,
    TESTING_PAGE_TYPE,
)
from app.parsers.pdf_parser import (
    ParsedPage,
    ParsedPdf,
    PdfVectorPrimitive,
    Span,
)
from tests.helpers.compiled_catalog import (
    _note_page_pdf,
    _pdf,
    _rule,
    _two_row_table_pdf,
    execute_pdf_rules,
)


def test_unit_conversion_rules_ignore_two_row_tables() -> None:
    cases = [
        (
            "CUSTOM_PASCAL_INHG_CONVERSION",
            [
                ("101.325 kPa", "No conversion"),
                ("202.65 kPa", "No conversion"),
            ],
        ),
        (
            "CUSTOM_TEMPERATURE_FAHRENHEIT",
            [
                ("Temperature: 15 deg. C", "No conversion"),
                ("Temperature: 20 deg. C", "No conversion"),
            ],
        ),
    ]

    for rule_code, rows in cases:
        results, suggestions = execute_pdf_rules(
            _two_row_table_pdf(rows),
            [_rule(rule_code)],
        )

        assert results[0].status == "PASS", rule_code
        assert suggestions == [], rule_code


def _note_page_pdf_with_lines(lines: list[str], page_type: str) -> ParsedPdf:
    text = "\n".join(lines)
    spans = [
        Span(
            text=line,
            bbox=(40.0, 100.0 + index * 20.0, 500.0, 112.0 + index * 20.0),
            page=1,
            font="Arial",
            size=10.0,
        )
        for index, line in enumerate(lines)
    ]
    page = ParsedPage(page=1, text=text, spans=spans, page_type=page_type)
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def test_note_page_rules_require_categories_inside_note_and_exact_values() -> None:
    repair_rh = (
        "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00, "
        "F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
    )
    storage_temperature = (
        "Temperature: Refer to Standard Practices Manual ATA No. 20-02-00, "
        "F9111CMON-A-20-02-00-00A-812A-A – Storage and Transportation of Assemblies."
    )
    repair_note_intro = (
        "NOTE: During repair operations, make sure that the environmental "
        "conditions are as follows:"
    )
    testing_note_intro = (
        "NOTE: During testing operations, make sure that the environmental "
        "conditions are as follows:"
    )
    storage_note_intro = (
        "NOTE: During storage operations, make sure that the environmental "
        "conditions are as follows:"
    )

    repair_rule = _rule("CUSTOM_REPAIR_NOTE")
    repair_valid, _ = execute_pdf_rules(
        _note_page_pdf(
            f"REPAIR\n{repair_note_intro}\nPressure: 1 bar\n{repair_rh}",
            REPAIR_PAGE_TYPE,
        ),
        [repair_rule],
    )
    repair_outside_note, _ = execute_pdf_rules(
        _note_page_pdf(f"REPAIR\nPressure: 1 bar\nNOTE\n{repair_rh}", REPAIR_PAGE_TYPE),
        [repair_rule],
    )
    repair_uppercase, _ = execute_pdf_rules(
        _note_page_pdf(
            f"REPAIR\n{repair_note_intro}\nPRESSURE: 1 bar\n{repair_rh}",
            REPAIR_PAGE_TYPE,
        ),
        [repair_rule],
    )
    repair_missing_intro, _ = execute_pdf_rules(
        _note_page_pdf(f"REPAIR\nNOTE\nPressure: 1 bar\n{repair_rh}", REPAIR_PAGE_TYPE),
        [repair_rule],
    )
    repair_wrong_intro, _ = execute_pdf_rules(
        _note_page_pdf(
            f"REPAIR\n{testing_note_intro}\nPressure: 1 bar\n{repair_rh}",
            REPAIR_PAGE_TYPE,
        ),
        [repair_rule],
    )
    repair_outside_page, repair_outside_page_suggestions = execute_pdf_rules(
        _note_page_pdf(f"OTHER\nNOTE\nPRESSURE: 1 bar\n{repair_rh}", "OTHER"),
        [repair_rule],
    )

    testing_rule = _rule("CUSTOM_TESTING_NOTE")
    testing_valid, _ = execute_pdf_rules(
        _note_page_pdf(
            f"TESTING\n{testing_note_intro}\nPressure: 1 bar\n- {repair_rh}\n"
            "Temperature: 20 deg. C",
            TESTING_PAGE_TYPE,
        ),
        [testing_rule],
    )
    testing_wrong_rh, _ = execute_pdf_rules(
        _note_page_pdf(
            f"TESTING\n{testing_note_intro}\nPressure: 1 bar\n"
            "Relative humidity: 50%\nTemperature: 20 deg. C",
            TESTING_PAGE_TYPE,
        ),
        [testing_rule],
    )

    storage_rule = _rule("CUSTOM_STORAGE_NOTE")
    storage_valid, _ = execute_pdf_rules(
        _note_page_pdf(
            f"STORAGE\n{storage_note_intro}\nPressure: 1 bar\n{repair_rh}\n"
            f"{storage_temperature}",
            STORAGE_PAGE_TYPE,
        ),
        [storage_rule],
    )
    storage_wrong_temperature, _ = execute_pdf_rules(
        _note_page_pdf(
            f"STORAGE\n{storage_note_intro}\nPressure: 1 bar\n{repair_rh}\n"
            "Temperature: 20 deg. C",
            STORAGE_PAGE_TYPE,
        ),
        [storage_rule],
    )
    accented_repair_rh = repair_rh.replace("procedure.", "proc\u00e9dure.")
    replacement_temperature = storage_temperature.replace("–", "\uFFFD").replace(
        "Assemblies", "assemblies"
    )
    storage_text_variants, _ = execute_pdf_rules(
        _note_page_pdf(
            f"STORAGE\n{storage_note_intro}\nPressure: 1 bar\n"
            f"{accented_repair_rh}\n{replacement_temperature}",
            STORAGE_PAGE_TYPE,
        ),
        [storage_rule],
    )

    assert repair_valid[0].status == "PASS"
    assert repair_outside_note[0].status == "FAIL"
    assert repair_uppercase[0].status == "FAIL"
    assert repair_missing_intro[0].status == "FAIL"
    assert repair_wrong_intro[0].status == "FAIL"
    assert repair_outside_page == []
    assert repair_outside_page_suggestions == []
    assert testing_valid[0].status == "PASS"
    assert testing_wrong_rh[0].status == "FAIL"
    assert storage_valid[0].status == "PASS"
    assert storage_wrong_temperature[0].status == "FAIL"
    assert storage_text_variants[0].status == "PASS"


def test_note_suggestions_ignore_list_markers_and_anchor_missing_storage_paragraph() -> None:
    repair_rh = (
        "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00, "
        "F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
    )
    testing_intro = (
        "NOTE: During testing operations, make sure that the environmental "
        "conditions are as follows:"
    )
    storage_intro = (
        "NOTE: During storage operations, make sure that the environmental "
        "conditions are as follows:"
    )
    storage_temperature = (
        "Temperature: Refer to Standard Practices Manual ATA No. 20-02-00, "
        "F9111CMON-A-20-02-00-00A-812A-A – Storage and Transportation of Assemblies."
    )

    testing_prefix = "- Relative humidity: "
    testing_error = "DMC"
    testing_suffix = (
        "Refer to Standard Practices Manual ATA No. 20-02-00, "
        "F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
    )
    testing_lines = [
        "TESTING",
        testing_intro,
        "Pressure: 1 bar",
        testing_prefix + testing_error + " " + testing_suffix,
        "Temperature: 20 deg. C",
    ]
    testing_text = "\n".join(testing_lines)
    testing_spans = [
        Span(
            text=testing_lines[0],
            bbox=(40.0, 100.0, 500.0, 112.0),
            page=1,
            font="Arial",
            size=10.0,
        ),
        Span(
            text=testing_lines[1],
            bbox=(40.0, 120.0, 500.0, 132.0),
            page=1,
            font="Arial",
            size=10.0,
        ),
        Span(
            text=testing_lines[2],
            bbox=(40.0, 140.0, 500.0, 152.0),
            page=1,
            font="Arial",
            size=10.0,
        ),
        Span(
            text=testing_prefix,
            bbox=(40.0, 160.0, 170.0, 172.0),
            page=1,
            font="Arial",
            size=10.0,
        ),
        Span(
            text=testing_error,
            bbox=(170.0, 160.0, 195.0, 172.0),
            page=1,
            font="Arial",
            size=10.0,
        ),
        Span(
            text=testing_suffix,
            bbox=(195.0, 160.0, 500.0, 172.0),
            page=1,
            font="Arial",
            size=10.0,
        ),
        Span(
            text=testing_lines[4],
            bbox=(40.0, 180.0, 500.0, 192.0),
            page=1,
            font="Arial",
            size=10.0,
        ),
    ]
    testing_page = ParsedPage(
        page=1,
        text=testing_text,
        spans=testing_spans,
        page_type=TESTING_PAGE_TYPE,
    )
    testing_results, testing_suggestions = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[testing_page],
            full_text=testing_text,
            is_signed=False,
        ),
        [_rule("CUSTOM_TESTING_NOTE")],
    )

    storage_lines = [
        "STORAGE",
        storage_intro,
        "Pressure: 1 bar",
        repair_rh,
    ]
    storage_results, storage_suggestions = execute_pdf_rules(
        _note_page_pdf_with_lines(storage_lines, STORAGE_PAGE_TYPE),
        [_rule("CUSTOM_STORAGE_NOTE")],
    )

    assert testing_results[0].status == "FAIL"
    assert len(testing_suggestions) == 1
    assert testing_suggestions[0].original == testing_error
    assert testing_suggestions[0].proposed == ""
    assert testing_suggestions[0].bbox == (170.0, 160.0, 195.0, 172.0)

    assert storage_results[0].status == "FAIL"
    assert len(storage_suggestions) == 1
    assert storage_suggestions[0].original == ""
    assert storage_suggestions[0].proposed == storage_temperature
    assert storage_suggestions[0].bbox is not None
    assert storage_suggestions[0].bbox[1] > 172.0
    assert storage_suggestions[0].bbox[2] <= 500.0


def test_repair_note_typo_split_across_pdf_lines_emits_one_local_suggestion() -> None:
    lines = [
        "REPAIR",
        "NOTE: During repair operations, make sure that the environmental conditions",
        "are as follows:",
        "- Pressure: No specific environmental level other than the ambient pressure level",
        "is necessary.",
        "- Relative humidity: Refer to Standard Practices Manual ATA No.",
        "20-00-02, F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure.",
    ]

    results, suggestions = execute_pdf_rules(
        _note_page_pdf_with_lines(lines, REPAIR_PAGE_TYPE),
        [_rule("CUSTOM_REPAIR_NOTE")],
    )

    assert results[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in suggestions] == [
        ("0-02", "2-00")
    ]


def test_temperature_in_celsius_requires_a_parenthesized_fahrenheit_conversion() -> None:
    rule = _rule("CUSTOM_TEMPERATURE_FAHRENHEIT")
    valid, valid_suggestions = execute_pdf_rules(
        _pdf("Temperature: 15 to 35 deg. C (59 to 95 deg. F)"),
        [rule],
    )
    materials, materials_suggestions = execute_pdf_rules(
        _pdf("LIST OF MATERIALS\nTemperature: 15 deg. C"),
        [rule],
    )
    missing, missing_suggestions = execute_pdf_rules(
        _pdf("Temperature: 15 to 35 deg. C"),
        [rule],
    )
    misplaced, misplaced_suggestions = execute_pdf_rules(
        _pdf("Temperature: 15 to 35 deg. C; equivalent to 59 to 95 deg. F"),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert materials[0].status == "PASS"
    assert materials_suggestions == []
    assert missing[0].status == "FAIL"
    assert missing_suggestions[0].original == "Temperature: 15 to 35 deg. C"
    assert missing_suggestions[0].proposed == (
        "Temperature: 15 to 35 deg. C (59 to 95 deg. F)"
    )
    assert misplaced[0].status == "FAIL"
    assert misplaced_suggestions[0].original == "Temperature: 15 to 35 deg. C"
    assert misplaced_suggestions[0].proposed == (
        "Temperature: 15 to 35 deg. C (59 to 95 deg. F)"
    )


def test_temperature_ranges_use_deg_c_only_after_the_second_value() -> None:
    rule = _rule("CUSTOM_TEMPERATURE_RANGE_FORMAT")
    valid, valid_suggestions = execute_pdf_rules(
        _pdf("Temperature: 15 to 35 deg. C (59 to 95 deg. F)"),
        [rule],
    )
    invalid_cases = (
        "Temperature: 15 deg. C to 35 deg. C",
        "Temperature: 15 C to 35 deg. C",
        "Temperature: 15 to 35 C",
        "Temperature: 15 to 35",
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    for text in invalid_cases:
        results, suggestions = execute_pdf_rules(_pdf(text), [rule])
        assert results[0].status == "FAIL", text
        assert len(suggestions) == 1, text
        assert suggestions[0].proposed == "", text


def test_bar_pressure_requires_a_parenthesized_psi_conversion() -> None:
    rule = _rule("CUSTOM_BAR_PSI_CONVERSION")
    valid, valid_suggestions = execute_pdf_rules(
        _pdf("Pressure: 0.7 bar (10.15 p.s.i.)"),
        [rule],
    )
    missing, missing_suggestions = execute_pdf_rules(
        _pdf("Pressure: 0.7 bar"),
        [rule],
    )
    wrong_unit, wrong_unit_suggestions = execute_pdf_rules(
        _pdf("Pressure: 0.7 bar (20.67 inHg)"),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert missing[0].status == "FAIL"
    assert missing_suggestions[0].original == "0.7 bar"
    assert missing_suggestions[0].proposed == "0.7 bar (10.15 p.s.i.)"
    wrong_value, wrong_value_suggestions = execute_pdf_rules(
        _pdf("Pressure: 0.7 bar (10.25 p.s.i.)"),
        [rule],
    )
    assert wrong_unit[0].status == "FAIL"
    assert wrong_unit_suggestions[0].original == "0.7 bar (20.67 inHg)"
    assert wrong_unit_suggestions[0].proposed == "0.7 bar (10.15 p.s.i.)"
    assert wrong_value[0].status == "FAIL"
    assert wrong_value_suggestions[0].original == "0.7 bar (10.25 p.s.i.)"
    assert wrong_value_suggestions[0].proposed == "0.7 bar (10.15 p.s.i.)"

    tolerance, tolerance_suggestions = execute_pdf_rules(
        _pdf("Pressure: 0.7 bar + 3% (10.15 p.s.i. + 3%)"),
        [rule],
    )
    assert tolerance[0].status == "PASS"
    assert tolerance_suggestions == []


def test_thales_si_units_require_parenthesized_imperial_conversions() -> None:
    cases = [
        (
            "CUSTOM_PASCAL_INHG_CONVERSION",
            "Pressure: 101.325 kPa +- 3% (29.92 inHg + 3%)",
            "Pressure: 101.325 kPa + 3% (30.10 inHg + 3%)",
            "101.325 kPa + 3% (29.92 inHg + 3%)",
        ),
        (
            "CUSTOM_METRIC_LENGTH_INCH_CONVERSION",
            "Length: 2.54 cm +- 3% (1.00 in. + 3%)",
            "Length: 2.54 cm + 3% (1.10 in. + 3%)",
            "2.54 cm + 3% (1.00 in. + 3%)",
        ),
        (
            "CUSTOM_METRIC_MASS_LBF_CONVERSION",
            "Mass: 400 g +- 3% (0.882 lb + 3%)",
            "Mass: 400 g + 3% (0.90 lb + 3%)",
            "400 g + 3% (0.882 lb + 3%)",
        ),
        (
            "CUSTOM_METRIC_MASS_LBF_CONVERSION",
            "Mass: 400 g +- 3% (0.882 lb +- 3%)",
            "Mass: 400 g +- 3% (0.90 lb +- 2%)",
            "400 g +- 3% (0.882 lb +- 3%)",
        ),
        (
            "CUSTOM_METRIC_TORQUE_LBF_IN_CONVERSION",
            "Torque: 1 daN.m +- 3% (88.51 lbf.in + 3%)",
            "Torque: 1 daN.m + 3% (88.00 lbf.in + 3%)",
            "1 daN.m + 3% (88.51 lbf.in + 3%)",
        ),
    ]

    for rule_code, valid_text, invalid_text, expected_proposal in cases:
        rule = _rule(rule_code)
        valid, valid_suggestions = execute_pdf_rules(_pdf(valid_text), [rule])
        invalid, invalid_suggestions = execute_pdf_rules(_pdf(invalid_text), [rule])

        assert valid[0].status == "PASS", rule_code
        assert valid_suggestions == [], rule_code
        assert invalid[0].status == "FAIL", rule_code
        assert invalid_suggestions[0].proposed == expected_proposal, rule_code


def test_metric_length_conversion_skips_table_but_checks_body_text() -> None:
    rows = [
        ("1", "200001", "Washer 2.5 mm"),
        ("2", "200002", "Spacer 4 mm, Temperature: 15 deg. C"),
        ("3", "200003", "Sleeve 6 mm"),
    ]
    lines: list[str] = []
    spans: list[Span] = []
    for row_index, cells in enumerate(rows):
        y = 100.0 + row_index * 20.0
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
    body_lines = ["Outside the table: 25.4 mm", "Temperature: 15 deg. C"]
    lines.extend(body_lines)
    for row_index, body_line in enumerate(body_lines, start=3):
        y = 100.0 + row_index * 20.0
        spans.append(
            Span(
                text=body_line,
                bbox=(40.0, y, 250.0, y + 12.0),
                page=1,
                font="Arial",
                size=10.0,
            )
        )
    text = "\n".join(lines)
    page = ParsedPage(page=1, text=text, spans=spans, page_height=792.0)
    parsed = ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)

    results, suggestions = execute_pdf_rules(
        parsed,
        [_rule("CUSTOM_METRIC_LENGTH_INCH_CONVERSION")],
    )

    assert results[0].status == "FAIL"
    assert [(suggestion.original, suggestion.proposed) for suggestion in suggestions] == [
        ("25.4 mm", "25.4 mm (1.00 in.)")
    ]

    temperature_results, temperature_suggestions = execute_pdf_rules(
        parsed,
        [_rule("CUSTOM_TEMPERATURE_FAHRENHEIT")],
    )

    assert temperature_results[0].status == "FAIL"
    assert [suggestion.original for suggestion in temperature_suggestions] == [
        "Temperature: 15 deg. C"
    ]


@pytest.mark.parametrize(
    ("rule_code", "measurement"),
    [
        ("CUSTOM_METRIC_LENGTH_INCH_CONVERSION", "25.4 mm"),
        ("CUSTOM_METRIC_MASS_LBF_CONVERSION", "1 kg"),
        ("CUSTOM_METRIC_TORQUE_LBF_IN_CONVERSION", "1 N.m"),
    ],
)
def test_metric_conversions_skip_vector_bordered_table_cells(
    rule_code: str,
    measurement: str,
) -> None:
    page = ParsedPage(
        page=1,
        text=f"Capacity {measurement}",
        spans=[
            Span(
                text=f"Capacity {measurement}",
                bbox=(297.2, 111.0, 381.2, 125.0),
                page=1,
                font="Arial",
                size=10.0,
            )
        ],
        page_height=792.0,
        vector_primitives=[
            PdfVectorPrimitive("rect", (50.0, y, 528.0, y + 0.5), None, None, 0.0)
            for y in (90.0, 110.0, 130.0, 150.0)
        ],
    )
    parsed = ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False)

    results, suggestions = execute_pdf_rules(parsed, [_rule(rule_code)])

    assert results[0].status == "PASS", rule_code
    assert suggestions == [], rule_code


def test_forbidden_consumables_are_reported_by_one_rule() -> None:
    rule = _rule("CUSTOM_FORBIDDEN_CONSUMABLES")

    valid, valid_suggestions = execute_pdf_rules(
        _pdf("Use approved packaging."),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _pdf("Use Silica gel, dessicant bag, desiccant, freon, and flugene."),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert {item.original for item in invalid_suggestions} == {
        "Silica gel",
        "dessicant bag",
        "desiccant",
        "freon",
        "flugene",
    }
    assert {item.proposed for item in invalid_suggestions} == {""}
    assert {item.rule_code for item in invalid_suggestions} == {
        "CUSTOM_FORBIDDEN_CONSUMABLES"
    }


def test_legacy_thales_references_are_proposed_as_thales() -> None:
    rule = _rule("CUSTOM_REPLACE_LEGACY_NAMES")

    valid, valid_suggestions = execute_pdf_rules(
        _pdf("Use THALES equipment."),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _pdf("AVIONICS, Sextant and thomson equipment."),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert [item.original for item in invalid_suggestions] == [
        "AVIONICS",
        "Sextant",
        "thomson",
    ]
    assert {item.proposed for item in invalid_suggestions} == {"THALES"}


def test_temperature_unit_symbols_are_replaced_with_deg_notation() -> None:
    celsius_rule = _rule("CUSTOM_NO_DEGREE_C_SYMBOL")
    fahrenheit_rule = _rule("CUSTOM_NO_DEGREE_F_SYMBOL")

    valid, valid_suggestions = execute_pdf_rules(
        _pdf("Temperature: 15 to 35 deg. C (59 to 95 deg. F)"),
        [celsius_rule, fahrenheit_rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _pdf("Temperature: 15 to 35 °C (59 to 95 °F)"),
        [celsius_rule, fahrenheit_rule],
    )

    assert [result.status for result in valid] == ["PASS", "PASS"]
    assert valid_suggestions == []
    assert [result.status for result in invalid] == ["FAIL", "FAIL"]
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        ("°C", "deg. C"),
        ("°F", "deg. F"),
    ]
