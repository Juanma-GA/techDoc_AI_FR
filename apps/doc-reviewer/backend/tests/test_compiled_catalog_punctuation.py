"""Compiled catalog: sentence and enumeration punctuation rules."""

from __future__ import annotations

import pytest

from app.core.compiled_rule_operators import sentence_punctuation_issues
from app.parsers.pdf_parser import (
    ParsedPage,
    ParsedPdf,
    Span,
)
from tests.helpers.compiled_catalog import (
    _pdf,
    _rule,
    _two_row_table_pdf,
    execute_pdf_rules,
)


def test_letter_digit_confusion_rule_flags_words_not_identifiers() -> None:
    rule = _rule("CUSTOM_LETTER_DIGIT_CONFUSION")
    suspicious = _pdf(
        "1llustration, illustrat1ion, s3ction; numeric reference 1l00."
    )
    suspicious.pages[0].is_modified = True
    ordinary = _pdf("TP1, A320, F9111CMON, JZAGO3OTL and JZAGO1OTL.")
    ordinary.pages[0].is_modified = True

    suspicious_results, _ = execute_pdf_rules(suspicious, [rule])
    ordinary_results, _ = execute_pdf_rules(ordinary, [rule])

    assert suspicious_results[0].status == "FAIL"
    assert ordinary_results[0].status == "PASS"


def test_modified_pages_require_sentence_and_enumeration_punctuation() -> None:
    missing_rule = _rule("CUSTOM_SENTENCE_PUNCTUATION")
    swap_rule = _rule("CUSTOM_ENUMERATION_PUNCTUATION_SWAP")
    valid_page = ParsedPage(
        page=1,
        text=(
            "1. General\n\n"
            "This sentence is wrapped over two lines\n"
            "and ends with a full stop.\n\n"
            "- first item,\n\n"
            "- last item."
        ),
        spans=[],
        is_modified=True,
    )
    invalid_page = ParsedPage(
        page=1,
        text=(
            "A sentence without a full stop\n\n"
            "- first item.\n\n"
            "- missing middle item\n\n"
            "- last item,"
        ),
        spans=[],
        is_modified=True,
    )

    valid, valid_suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[valid_page], full_text=valid_page.text, is_signed=False),
        [missing_rule, swap_rule],
    )
    invalid_missing, missing_suggestions = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[invalid_page],
            full_text=invalid_page.text,
            is_signed=False,
        ),
        [missing_rule],
    )
    invalid_swaps, swap_suggestions = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[invalid_page],
            full_text=invalid_page.text,
            is_signed=False,
        ),
        [swap_rule],
    )

    assert [result.status for result in valid] == ["PASS", "PASS"]
    assert valid_suggestions == []
    assert invalid_missing[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in missing_suggestions] == [
        ("A sentence without a full stop", "A sentence without a full stop."),
        ("- missing middle item", "- missing middle item,"),
    ]
    assert invalid_swaps[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in swap_suggestions] == [
        ("- first item.", "- first item,"),
        ("- last item,", "- last item."),
    ]

    semicolon_page = ParsedPage(
        page=1,
        text="- first item;\n- second item;\n- last item,",
        is_modified=True,
    )
    semicolon_results, semicolon_suggestions = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[semicolon_page],
            full_text=semicolon_page.text,
            is_signed=False,
        ),
        [missing_rule, swap_rule],
    )

    assert [result.status for result in semicolon_results] == ["FAIL", "PASS"]
    assert [(item.original, item.proposed) for item in semicolon_suggestions] == [
        ("- last item,", "- last item;")
    ]


@pytest.mark.parametrize(
    ("marks", "expected_mark", "mismatched_index"),
    [
        ([".", ".", ".", ","], ".", 3),
        ([";", ";", ";", ","], ";", 3),
        ([",", ",", ",", "."], ",", 3),
        (["", "", "", ","], "", 3),
    ],
)
def test_enumeration_punctuation_follows_the_dominant_separator(
    marks: list[str],
    expected_mark: str,
    mismatched_index: int,
) -> None:
    lines = [
        f"- item {index + 1}{mark}"
        for index, mark in enumerate(marks)
    ]
    issues = sentence_punctuation_issues("\n".join(lines))

    assert [(issue.original, issue.proposed, issue.expected) for issue in issues] == [
        (
            lines[mismatched_index],
            f"- item {mismatched_index + 1}{expected_mark}",
            expected_mark,
        )
    ]


def test_sentence_punctuation_rule_ignores_unchanged_pages() -> None:
    rule = _rule("CUSTOM_SENTENCE_PUNCTUATION")
    page = ParsedPage(
        page=1,
        text="A sentence without a full stop",
        spans=[],
        is_modified=False,
    )

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False),
        [rule],
    )

    assert results[0].status == "INCONCLUSIVE"
    assert suggestions == []


def test_parenthesized_steps_are_excluded_from_punctuation_validation() -> None:
    rule = _rule("CUSTOM_SENTENCE_PUNCTUATION")
    page = ParsedPage(
        page=1,
        text="(1) First step.\n\n(2) Second step.\n\n(a) Substep.\n\n(b) Last substep.",
        spans=[],
        is_modified=True,
    )

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False),
        [rule],
    )

    assert results[0].status == "PASS"
    assert suggestions == []

    missing_period = ParsedPage(
        page=1,
        text="(1) First step,\n\n(2) Last step.\n\n(a) Substep,\n\n(b) Last substep",
        spans=[],
        is_modified=True,
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[missing_period],
            full_text=missing_period.text,
            is_signed=False,
        ),
        [rule],
    )

    assert invalid[0].status == "PASS"
    assert invalid_suggestions == []


def test_sentence_punctuation_rule_ignores_multi_column_table_cells() -> None:
    rule = _rule("CUSTOM_SENTENCE_PUNCTUATION")
    table_rows = [
        (450.0, [("Pressure", 175.0), ("Pressure", 256.0), ("R 1", 357.0), ("R 2", 438.0)]),
        (465.0, [("applied", 178.0), ("applied", 259.0), ("(ohms)", 348.0), ("(ohms)", 429.0)]),
        (480.0, [("(bars)", 181.0), ("(p.s.i)", 259.0)]),
        (510.0, [("0", 196.0), ("0", 281.0), ("22.5", 354.0), ("99.5", 435.0)]),
        (525.0, [("1", 196.0), ("14.50", 269.0), ("35.3", 354.0), ("86.7", 435.0)]),
        (540.0, [("2", 196.0), ("29", 278.0), ("48.1", 354.0), ("73.9", 435.0)]),
        (555.0, [("3", 196.0), ("43.50", 269.0), ("61", 360.0), ("61", 441.0)]),
    ]
    spans = [
        Span("Body text.", (40.0, 100.0, 120.0, 112.0), 1, "Arial", 10.0),
    ]
    for y, cells in table_rows:
        spans.extend(
            Span(text, (x, y, x + max(12.0, len(text) * 6.0), y + 12.0), 1, "Arial", 10.0)
            for text, x in cells
        )
    spans.append(Span("Footer", (40.0, 780.0, 80.0, 792.0), 1, "Arial", 10.0))
    page = ParsedPage(
        page=1,
        text="\n".join(span.text for span in spans),
        spans=spans,
        is_modified=True,
    )

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False),
        [rule],
    )

    assert results[0].status == "PASS"
    assert suggestions == []


def test_sentence_punctuation_ignores_wrapped_table_rows() -> None:
    rule = _rule("CUSTOM_SENTENCE_PUNCTUATION")
    row_data = [
        ("AMDt.", 107.6, 419.9),
        ("BRIEF DESCRIPTION", 230.2, 419.9),
        ("APPLICABLE TO VERSION", 420.1, 419.9),
        ("A", 118.9, 441.5),
        ("Elimination of 130C scale mark", 188.2, 441.5),
        ("From n 380", 450.1, 441.5),
        ("B", 118.9, 469.3),
        ("Dial colour zones made with four", 189.6, 462.2),
        ("Oct. 1981", 456.1, 469.3),
        ("coats paint", 188.8, 476.3),
        ("C", 118.9, 497.0),
        ("Replacement of the shield plate", 188.2, 497.0),
        ("Apr. 2001", 456.1, 497.0),
    ]
    spans = [
        Span(
            text,
            (x, y, x + max(12.0, len(text) * 6.0), y + 14.2),
            1,
            "Arial",
            10.0,
        )
        for text, x, y in row_data
    ]
    page = ParsedPage(
        page=1,
        text="\n".join(span.text for span in spans),
        spans=spans,
        is_modified=True,
    )

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False),
        [rule],
    )

    assert results[0].status == "PASS"
    assert suggestions == []


def test_sentence_punctuation_ignores_two_column_tables() -> None:
    rule = _rule("CUSTOM_SENTENCE_PUNCTUATION")
    rows = [
        ("AR:", "As Required"),
        ("DET:", "Detail"),
        ("EFF:", "Effectivity"),
        ("SUPSDS:", "Supersedes"),
    ]
    spans = []
    for index, (label, description) in enumerate(rows):
        y = 450.0 + index * 15.0
        spans.extend(
            [
                Span(label, (120.0, y, 180.0, y + 12.0), 1, "Arial", 10.0),
                Span(description, (280.0, y, 400.0, y + 12.0), 1, "Arial", 10.0),
            ]
        )
    page = ParsedPage(
        page=1,
        text="\n".join(f"{label} {description}" for label, description in rows),
        spans=spans,
        is_modified=True,
    )

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False),
        [rule],
    )

    assert results[0].status == "PASS"
    assert suggestions == []


def test_sentence_punctuation_ignores_figure_titles_and_column_labels() -> None:
    text = (
        "Then refer to the EDI to find:\n"
        "- The figure and item number of the component in the Detailed Parts\n"
        "List\n"
        "- 1st column: Figure Item - Figure and Item number\n\n"
        "Figure 12: Pump assembly\n\n"
        "Fig. 13: Pump assembly\n\n"
        "Figure 301A Schematic without terminal punctuation\n\n"
        "Figure X: Detail without terminal punctuation"
    )

    assert sentence_punctuation_issues(text) == []


def test_sentence_punctuation_ignores_two_row_tables() -> None:
    rule = _rule("CUSTOM_SENTENCE_PUNCTUATION")
    parsed = _two_row_table_pdf(
        [
            ("A sentence without its final punctuation", "Column value one"),
            ("Another sentence without its final punctuation", "Column value two"),
        ]
    )

    results, suggestions = execute_pdf_rules(parsed, [rule])

    assert results[0].status == "PASS"
    assert suggestions == []
