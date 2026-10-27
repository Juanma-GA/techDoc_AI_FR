"""Coverage for the built-in standards expressed as CompiledRule."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.checks.client_registry import load_active_client_configuration
from app.checks.standards import BUILTIN_STANDARDS, serialize_builtin_version
from app.checks.thales_rules.operations import shop_verification_text
from app.checks.thales_rules.page_classifier import (
    HIGHLIGHTS_PAGE_TYPE,
    HIGHLIGHTS_FIRST_PAGE_TYPE,
    INTRODUCTION_PAGE_TYPE,
    NUMERICAL_INDEX_PAGE_TYPE,
    TP2_PAGE_TYPE,
    REPAIR_PAGE_TYPE,
    STORAGE_PAGE_TYPE,
    TESTING_PAGE_TYPE,
    TP1_PAGE_TYPE,
    classify_pages,
    identify_note_pages,
    identify_numerical_index_pages,
    identify_introduction_pages,
    identify_tp1_pages,
)
from app.checks.thales_rules.rules import (
    DOCUMENT_TYPES,
    IMPORTANT_NOTICE_TEXT as _IMPORTANT_NOTICE_TEXT,
)

from app.core.compiled_rule_executor import execute_docx_rules, execute_pdf_rules as _execute_pdf_rules
from app.core.compiled_rule_operators import extract_year, sentence_punctuation_issues
from app.core.page_range import filter_pdf_pages
from app.core.compiled_rules import CompiledRule
from app.core.standard_rule_compiler import compile_standard_rule
from app.parsers.docx_parser import Block
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, PdfBookmark, PdfLine, Span


_TEST_CLIENT_BUNDLE = load_active_client_configuration().bundle


def execute_pdf_rules(*args: Any, **kwargs: Any):
    kwargs.setdefault("client_operations", _TEST_CLIENT_BUNDLE.operations)
    kwargs.setdefault("client_entities", _TEST_CLIENT_BUNDLE.mapping.entities)
    return _execute_pdf_rules(*args, **kwargs)


def _rule(code: str) -> CompiledRule:
    for spec in BUILTIN_STANDARDS:
        for label in spec["versions"]:
            for rule in spec["versions"][label]:
                if rule.id == code:
                    return rule
    for definition in _TEST_CLIENT_BUNDLE.rules:
        if definition.code == code:
            return definition.compiled_rule
    raise AssertionError(f"Unknown built-in rule: {code}")


def _pdf(text: str) -> ParsedPdf:
    page = ParsedPage(page=1, text=text, spans=[])
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def _two_row_table_pdf(rows: list[tuple[str, str]]) -> ParsedPdf:
    lines: list[str] = []
    spans: list[Span] = []
    for row_index, (left, right) in enumerate(rows):
        y = 200.0 + row_index * 20.0
        lines.append(f"{left} {right}")
        spans.extend(
            [
                Span(left, (40.0, y, 220.0, y + 12.0), 1, "Arial", 10.0),
                Span(right, (280.0, y, 500.0, y + 12.0), 1, "Arial", 10.0),
            ]
        )
    text = "\n".join(lines)
    page = ParsedPage(
        page=1,
        text=text,
        spans=spans,
        is_modified=True,
        page_height=792.0,
    )
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


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


def _highlights_structure_pdf(rows: list[tuple[str, str, str]]) -> ParsedPdf:
    spans = [
        Span("Chapter/Section and Page No", (54.0, 95.0, 200.0, 105.0), 1, "Arial", 10.0),
        Span("Designation", (285.0, 95.0, 330.0, 105.0), 1, "Arial", 10.0),
        Span("Description of Change", (366.0, 95.0, 480.0, 105.0), 1, "Arial", 10.0),
    ]
    for index, (pages, status, description) in enumerate(rows):
        y = 130.0 + index * 20.0
        if pages:
            spans.append(
                Span(pages, (90.7, y, 250.0, y + 10.0), 1, "Arial", 10.0)
            )
        if status:
            spans.append(
                Span(status, (322.2, y, 328.2, y + 10.0), 1, "Arial", 10.0)
            )
        if description:
            spans.append(
                Span(description, (366.0, y, 560.0, y + 10.0), 1, "Arial", 10.0)
            )
    text = "\n".join(span.text for span in spans)
    page = ParsedPage(
        page=1,
        text=text,
        spans=spans,
        page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
    )
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def _numbered_chapter_pdf(pages: list[tuple[str, list[str]]]) -> ParsedPdf:
    parsed_pages = []
    for physical_page, (page_key, headings) in enumerate(pages, start=1):
        spans = []
        lines = []
        for index, heading in enumerate(headings):
            y = 130.0 + index * 24.0
            bbox = (86.0, y, 500.0, y + 14.0)
            lines.append(PdfLine(heading, bbox, block_index=1, line_index=index))
            spans.append(Span(heading, bbox, physical_page, "Arial", 12.0))
        spans.extend(
            [
                Span("THALES AVS FRANCE SAS", (85.0, 755.0, 220.0, 765.0), physical_page, "Arial", 9.0),
                Span(f"Page {page_key}", (500.0, 755.0, 560.0, 765.0), physical_page, "Arial", 9.0),
                Span("JUL 27/26", (500.0, 771.0, 560.0, 781.0), physical_page, "Arial", 9.0),
            ]
        )
        text = "\n".join([*headings, "THALES AVS FRANCE SAS", f"Page {page_key}", "JUL 27/26"])
        parsed_pages.append(
            ParsedPage(
                page=physical_page,
                text=text,
                spans=spans,
                lines=lines,
                page_height=792.0,
            )
        )
    full_text = "\n".join(page.text for page in parsed_pages)
    return ParsedPdf(
        page_count=len(parsed_pages),
        pages=parsed_pages,
        full_text=full_text,
        is_signed=False,
    )


def _list_materials_code_pdf(rows: list[tuple[str, str, str]]) -> ParsedPdf:
    spans = [
        Span("LIST OF MATERIALS", (272.0, 100.0, 380.0, 114.0), 1, "Arial", 10.0),
        Span("DESIGNATION", (113.8, 230.0, 185.8, 244.0), 1, "Arial", 10.0),
        Span("CODE", (254.0, 208.0, 284.0, 222.0), 1, "Arial", 10.0),
        Span("(Refer to STANDARD PRACTICES ATA No. 20-02-00)", (210.0, 223.0, 320.0, 251.0), 1, "Arial", 10.0),
        Span("SUPPLIERS TRADE NAME", (340.7, 223.0, 466.7, 237.0), 1, "Arial", 10.0),
        Span("AND CODE FSCM", (361.7, 237.0, 445.7, 251.0), 1, "Arial", 10.0),
        Span("USE", (511.5, 218.0, 535.5, 232.0), 1, "Arial", 10.0),
        Span("THALES AVS FRANCE SAS", (50.0, 755.0, 210.0, 765.0), 1, "Arial", 9.0),
        Span("LM Page 1", (500.0, 755.0, 560.0, 765.0), 1, "Arial", 9.0),
        Span("JUL 30/26", (500.0, 771.0, 560.0, 781.0), 1, "Arial", 9.0),
    ]
    for index, (designation, code, supplier) in enumerate(rows):
        y = 266.0 + index * 22.0
        spans.extend(
            [
                Span(designation, (90.0, y, 192.0, y + 14.0), 1, "Arial", 10.0),
                Span(code, (210.5, y, 282.5, y + 14.0), 1, "Arial", 10.0),
                Span(supplier, (328.7, y, 430.7, y + 14.0), 1, "Arial", 10.0),
            ]
        )
    text = "\n".join(span.text for span in spans)
    page = ParsedPage(page=1, text=text, spans=spans, page_height=792.0)
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def _numerical_index_pdf(
    pages: list[list[str]],
    *,
    leading_pages: int = 0,
) -> ParsedPdf:
    parsed_pages = [
        ParsedPage(page=page_number, text="INTRODUCTION", page_height=792.0)
        for page_number in range(1, leading_pages + 1)
    ]
    for logical_page, part_numbers in enumerate(pages, start=1):
        physical_page = leading_pages + logical_page
        spans = [
            Span("NUMERICAL INDEX", (278.9, 100.0, 368.9, 114.0), physical_page, "Arial", 10.0),
            Span("PART NUMBER", (89.6, 122.0, 155.6, 136.0), physical_page, "Arial", 10.0),
            Span("AIRLINE", (311.6, 122.0, 353.6, 136.0), physical_page, "Arial", 10.0),
            Span("STOCK NO.", (311.6, 133.0, 365.6, 147.0), physical_page, "Arial", 10.0),
            Span("FIGURE", (454.8, 122.0, 490.8, 136.0), physical_page, "Arial", 10.0),
            Span("ITEM", (460.8, 133.0, 484.8, 147.0), physical_page, "Arial", 10.0),
            Span("TTL", (517.1, 122.0, 535.1, 136.0), physical_page, "Arial", 10.0),
            Span("REQ", (517.1, 133.0, 535.1, 147.0), physical_page, "Arial", 10.0),
            Span("THALES AVS FRANCE SAS", (85.0, 755.0, 220.0, 765.0), physical_page, "Arial", 9.0),
            Span(f"NI/NUM 1101 Page {logical_page}", (450.0, 755.0, 567.0, 765.0), physical_page, "Arial", 9.0),
            Span("JUL 30/26", (500.0, 771.0, 560.0, 781.0), physical_page, "Arial", 9.0),
        ]
        for index, part_number in enumerate(part_numbers):
            y = 160.0 + index * 16.0
            spans.extend(
                [
                    Span(part_number, (89.6, y, 180.0, y + 12.0), physical_page, "Arial", 10.0),
                    Span("21-33-13", (311.6, y, 365.6, y + 12.0), physical_page, "Arial", 10.0),
                ]
            )
        text = "\n".join(span.text for span in spans)
        parsed_pages.append(
            ParsedPage(page=physical_page, text=text, spans=spans, page_height=792.0)
        )
    full_text = "\n".join(page.text for page in parsed_pages)
    parsed = ParsedPdf(
        page_count=len(parsed_pages),
        pages=parsed_pages,
        full_text=full_text,
        is_signed=False,
    )
    identify_numerical_index_pages(parsed)
    return parsed


def _cmm_footer_pdf(footer: str, *, cmm_size: float = 8.0) -> ParsedPdf:
    body = "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00."
    text = f"{body}\n{footer}"
    page = ParsedPage(
        page=1,
        text=text,
        spans=[
            Span(text=body, bbox=(40.0, 100.0, 500.0, 120.0), page=1, font="Arial", size=10.0),
            Span(text=footer, bbox=(40.0, 760.0, 200.0, 780.0), page=1, font="Arial", size=cmm_size),
        ],
    )
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def _tp2_notice_pdf(notice: str, *, page_type: str | None = TP2_PAGE_TYPE) -> ParsedPdf:
    footer = "79-30-01\nTP 2\nJUL 27/26"
    text = f"{notice}\n{footer}"
    page = ParsedPage(
        page=1,
        text=text,
        page_type=page_type,
        spans=[
            Span(
                text=notice,
                bbox=(50.0, 120.0, 530.0, 648.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text=footer,
                bbox=(40.0, 752.0, 580.0, 780.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
        ],
    )
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def _logo_pdf(
    size: float,
    *,
    page_type: str | None = None,
    font: str = "Thales Plain",
    page_number: int = 1,
) -> ParsedPdf:
    logo = "T"
    body = "Document body."
    text = f"{logo}\n{body}"
    page = ParsedPage(
        page=page_number,
        text=text,
        page_type=page_type,
        spans=[
            Span(
                text=logo,
                bbox=(200.0, 10.0, 300.0, 40.0),
                page=page_number,
                font=font,
                size=size,
            ),
            Span(
                text=body,
                bbox=(40.0, 100.0, 200.0, 120.0),
                page=page_number,
                font="Arial",
                size=10.0,
            ),
        ],
    )
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def _title_page_copyright_pdf(footer: str) -> ParsedPdf:
    body = "Title page body."
    text = f"{body}\n{footer}"
    page = ParsedPage(
        page=1,
        text=text,
        spans=[
            Span(text=body, bbox=(40.0, 100.0, 200.0, 120.0), page=1, font="Arial", size=10.0),
            Span(text=footer, bbox=(40.0, 760.0, 580.0, 780.0), page=1, font="Arial", size=8.0),
        ],
    )
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def _title_page_copyright_pages(footers: dict[int, str]) -> ParsedPdf:
    pages: list[ParsedPage] = []
    for page_number, footer in sorted(footers.items()):
        body = f"Title page body {page_number}."
        text = f"{body}\n{footer}"
        pages.append(
            ParsedPage(
                page=page_number,
                text=text,
                spans=[
                    Span(
                        text=body,
                        bbox=(40.0, 100.0, 200.0, 120.0),
                        page=page_number,
                        font="Arial",
                        size=10.0,
                    ),
                    Span(
                        text=footer,
                        bbox=(40.0, 760.0, 580.0, 780.0),
                        page=page_number,
                        font="Arial",
                        size=8.0,
                    ),
                ],
            )
        )
    return ParsedPdf(
        page_count=max(footers),
        pages=pages,
        full_text="\n".join(page.text for page in pages),
        is_signed=False,
    )


def test_all_builtin_catalog_entries_round_trip_as_compiled_rules() -> None:
    total = 0
    for spec in BUILTIN_STANDARDS:
        metadata = spec["metadata"]
        for label in spec["versions"]:
            payloads = serialize_builtin_version(spec, label)
            total += len(payloads)
            assert all("id" in payload and "checks" in payload for payload in payloads)
            for payload in payloads:
                compiled = compile_standard_rule(payload, f"{spec['code']}:{label}")
                assert compiled is not None
                assert compiled.source == "standard_rule"
                assert metadata[compiled.id]["description_en"]
                assert metadata[compiled.id]["message"]
                assert metadata[compiled.id]["message_en"]
    assert total == 36


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


def test_user_cmm_rule_uses_the_document_context_value() -> None:
    rule = _rule("CUSTOM_CMM_NUMBER")

    valid, _ = execute_pdf_rules(
        _cmm_footer_pdf("79-30-02"),
        [rule],
        document=SimpleNamespace(meta_cmm_number="79-30-02"),
    )
    valid_with_a_suffix, _ = execute_pdf_rules(
        _cmm_footer_pdf("79-30-02A"),
        [rule],
        document=SimpleNamespace(meta_cmm_number="79-30-02"),
    )
    valid_with_a_suffix_in_mapping, _ = execute_pdf_rules(
        _cmm_footer_pdf("79-30-02A"),
        [rule],
        document=SimpleNamespace(meta_cmm_number="79-30-02A"),
    )
    invalid_with_other_suffix, _ = execute_pdf_rules(
        _cmm_footer_pdf("79-30-02B"),
        [rule],
        document=SimpleNamespace(meta_cmm_number="79-30-02"),
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _cmm_footer_pdf("79-33-02"),
        [rule],
        document=SimpleNamespace(meta_cmm_number="79-30-02"),
    )
    missing, _ = execute_pdf_rules(
        _cmm_footer_pdf("Page 1"),
        [rule],
        document=SimpleNamespace(meta_cmm_number="79-30-02"),
    )

    assert valid[0].status == "PASS"
    assert valid_with_a_suffix[0].status == "PASS"
    assert valid_with_a_suffix_in_mapping[0].status == "PASS"
    assert invalid_with_other_suffix[0].status == "FAIL"
    assert invalid[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        ("3", "0")
    ]
    assert missing[0].status == "FAIL"


def test_user_cmm_font_size_rule_accepts_pdf_rounding_and_rejects_wrong_size() -> None:
    rule = _rule("CUSTOM_CMM_NUMBER_FONT_SIZE")
    document = SimpleNamespace(meta_cmm_number="79-30-02")

    valid, _ = execute_pdf_rules(
        _cmm_footer_pdf("79-30-02", cmm_size=23.03),
        [rule],
        document=document,
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _cmm_footer_pdf("79-30-02", cmm_size=20.03),
        [rule],
        document=document,
    )

    assert valid[0].status == "PASS"
    assert invalid[0].status == "FAIL"
    assert invalid[0].evidence is not None
    assert invalid[0].evidence.observed_value == "20 pt"
    assert invalid[0].evidence.expected_value == "23 pt"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].original == "79-30-02"
    assert invalid_suggestions[0].proposed == ""
    assert invalid_suggestions[0].bbox == (40.0, 760.0, 200.0, 780.0)
    assert "20 pt" in invalid_suggestions[0].message
    assert "23 pt" in invalid_suggestions[0].message


def test_user_cmm_font_size_ignores_ata_references_in_body_paragraphs() -> None:
    rule = _rule("CUSTOM_CMM_NUMBER_FONT_SIZE")
    spans = [
        Span("Body", (40.0, 100.0, 100.0, 112.0), 1, "Arial", 10.0),
        Span(
            "ATA reference 79-30-02 appears in this paragraph",
            (40.0, 640.0, 470.0, 652.0),
            1,
            "Arial",
            10.0,
        ),
        Span("79-30-02", (40.0, 760.0, 200.0, 780.0), 1, "Arial", 23.0),
    ]
    page = ParsedPage(
        page=1,
        text="\n".join(span.text for span in spans),
        spans=spans,
        page_height=792.0,
    )

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False),
        [rule],
        document=SimpleNamespace(meta_cmm_number="79-30-02"),
    )

    assert results[0].status == "PASS"
    assert suggestions == []


def test_thales_logo_font_size_rules_split_normal_pages_from_tp1() -> None:
    normal_rule = _rule("CUSTOM_THALES_LOGO_FONT_SIZE")
    tp1_rule = _rule("CUSTOM_TP1_THALES_LOGO_FONT_SIZE")

    normal_valid, normal_valid_suggestions = execute_pdf_rules(
        _logo_pdf(30.96),
        [normal_rule],
    )
    normal_invalid, normal_invalid_suggestions = execute_pdf_rules(
        _logo_pdf(30.0),
        [normal_rule],
    )
    non_thales, _ = execute_pdf_rules(
        _logo_pdf(31.0, font="Arial"),
        [normal_rule],
    )
    normal_on_tp1, _ = execute_pdf_rules(
        _logo_pdf(30.96, page_type="TP1"),
        [normal_rule],
    )
    tp1_valid, tp1_valid_suggestions = execute_pdf_rules(
        _logo_pdf(36.03, page_type="TP1"),
        [tp1_rule],
    )
    tp1_invalid, tp1_invalid_suggestions = execute_pdf_rules(
        _logo_pdf(30.96, page_type="TP1"),
        [tp1_rule],
    )

    assert normal_valid[0].status == "PASS"
    assert normal_valid_suggestions == []
    assert normal_invalid[0].status == "FAIL"
    assert len(normal_invalid_suggestions) == 1
    assert normal_invalid_suggestions[0].original == "T"
    assert normal_invalid_suggestions[0].proposed == ""
    assert "30 pt" in normal_invalid_suggestions[0].message
    assert non_thales[0].status == "FAIL"
    assert normal_on_tp1 == []
    assert tp1_valid[0].status == "PASS"
    assert tp1_valid_suggestions == []
    assert tp1_invalid[0].status == "FAIL"
    assert len(tp1_invalid_suggestions) == 1
    assert "31 pt" in tp1_invalid_suggestions[0].message


def test_tp2_important_notice_matches_the_exact_ata100_model() -> None:
    rule = _rule("CUSTOM_TP2_IMPORTANT_NOTICE")

    valid, valid_suggestions = execute_pdf_rules(
        _tp2_notice_pdf(_IMPORTANT_NOTICE_TEXT),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _tp2_notice_pdf(_IMPORTANT_NOTICE_TEXT.replace("sole property", "sole propriety", 1)),
        [rule],
    )
    invalid_spacing, _ = execute_pdf_rules(
        _tp2_notice_pdf(
            _IMPORTANT_NOTICE_TEXT.replace("contained herein", "contained here in", 1)
        ),
        [rule],
    )
    missing, missing_suggestions = execute_pdf_rules(
        _tp2_notice_pdf("TP2 notice missing", page_type=TP2_PAGE_TYPE),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert invalid_spacing[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].proposed == "property"
    assert "Texte attendu" in invalid_suggestions[0].message
    assert invalid_suggestions[0].original == "propriety"
    assert missing[0].status == "FAIL"
    assert len(missing_suggestions) == 1
    assert missing_suggestions[0].original == ""


def test_classify_pages_identifies_tp2_from_footer_marker() -> None:
    parsed = _tp2_notice_pdf(_IMPORTANT_NOTICE_TEXT, page_type=None)
    classify_pages(
        parsed,
        SimpleNamespace(
            meta_revision_date="JUL 27/26",
            meta_cmm_number="79-30-02",
        ),
    )

    assert parsed.pages[0].page_type == TP2_PAGE_TYPE


def test_page_types_survive_an_incorrect_revision_date_mapping() -> None:
    parsed = ParsedPdf(
        page_count=2,
        pages=[
            _page_with_footer_lines(
                1,
                ["79-30-01", "Highlights Page 1", "JUL 27/26"],
            ),
            _page_with_footer_lines(
                2,
                ["79-30-01", "TP 2", "JUL 27/26"],
            ),
        ],
        full_text="",
        is_signed=False,
    )

    classify_pages(
        parsed,
        SimpleNamespace(
            meta_revision_date="AUG 27/26",
            meta_cmm_number="79-30-02",
        ),
    )

    assert [page.page_type for page in parsed.pages] == [
        HIGHLIGHTS_FIRST_PAGE_TYPE,
        TP2_PAGE_TYPE,
    ]


def test_highlights_rule_still_runs_when_mapping_anchors_are_wrong() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_ATA_NUMBER")
    document = SimpleNamespace(
        meta_revision_date="AUG 27/26",
        meta_cmm_number="79-30-02",
    )
    parsed = ParsedPdf(
        page_count=1,
        pages=[
            _page_with_footer_lines(
                1,
                [
                    "79-30-01",
                    "Highlights Page 1",
                    "JUL 27/26",
                    "ATA No 79-30-01",
                ],
            )
        ],
        full_text="",
        is_signed=False,
    )

    classify_pages(parsed, document)
    results, suggestions = execute_pdf_rules(parsed, [rule], document=document)

    assert parsed.pages[0].page_type == HIGHLIGHTS_FIRST_PAGE_TYPE
    assert results[0].status == "FAIL"
    assert suggestions[0].proposed == "ATA No 79-30-02"


def test_highlights_ata_rule_accepts_added_a_suffix_when_mapping_has_base() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_ATA_NUMBER")
    document = SimpleNamespace(
        meta_revision_date="AUG 27/26",
        meta_cmm_number="79-30-02",
    )
    parsed = ParsedPdf(
        page_count=1,
        pages=[
            _page_with_footer_lines(
                1,
                [
                    "79-30-02A",
                    "Highlights Page 1",
                    "JUL 27/26",
                    "ATA No 79-30-02A",
                ],
            )
        ],
        full_text="",
        is_signed=False,
    )

    classify_pages(parsed, document)
    results, suggestions = execute_pdf_rules(parsed, [rule], document=document)

    assert parsed.pages[0].page_type == HIGHLIGHTS_FIRST_PAGE_TYPE
    assert results[0].status == "PASS"
    assert suggestions == []


def test_cmm_number_is_checked_on_each_page() -> None:
    pages = []
    for page_number, footer in enumerate(
        ("Revision: JUL 27/26\n79-30-02", "Revision: JAN 27/26\n79-30-01"),
        start=1,
    ):
        body = f"Title page body {page_number}."
        pages.append(
            ParsedPage(
                page=page_number,
                text=f"{body}\n{footer}",
                spans=[
                    Span(
                        text=body,
                        bbox=(40.0, 100.0, 200.0, 120.0),
                        page=page_number,
                        font="Arial",
                        size=10.0,
                    ),
                    Span(
                        text=footer,
                        bbox=(40.0, 760.0, 300.0, 780.0),
                        page=page_number,
                        font="Arial",
                        size=8.0,
                    ),
                ],
            )
        )
    parsed = ParsedPdf(
        page_count=2,
        pages=pages,
        full_text="\n".join(page.text for page in pages),
        is_signed=False,
    )
    document = SimpleNamespace(meta_cmm_number="79-30-02", meta_revision_date="JUL 27/26")

    cmm_results, cmm_suggestions = execute_pdf_rules(
        parsed,
        [_rule("CUSTOM_CMM_NUMBER")],
        document=document,
    )
    assert cmm_results[0].status == "FAIL"
    assert [(item.page, item.original, item.proposed) for item in cmm_suggestions] == [
        (2, "1", "2")
    ]


def _tp1_revision_footer_pdf(
    footer: str,
    *,
    page_type: str | None = TP1_PAGE_TYPE,
) -> ParsedPdf:
    body = "Title page body."
    text = f"{body}\n{footer}"
    footer_lines = footer.splitlines()
    page = ParsedPage(
        page=1,
        text=text,
        page_type=page_type,
        spans=[
            Span(text=body, bbox=(40.0, 100.0, 200.0, 120.0), page=1, font="Arial", size=10.0),
            *[
                Span(
                    text=line,
                    bbox=(40.0, 760.0 + index * 16.0, 300.0, 770.0 + index * 16.0),
                    page=1,
                    font="Arial",
                    size=8.0,
                )
                for index, line in enumerate(footer_lines)
            ],
        ],
    )
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def test_tp1_revision_number_matches_document_context_value() -> None:
    rule = _rule("CUSTOM_TP1_REVISION_NUMBER")
    document = SimpleNamespace(meta_revision_number="04")

    valid, valid_suggestions = execute_pdf_rules(
        _tp1_revision_footer_pdf("Revision No.04\nFirst Issue: JUL 27/26"),
        [rule],
        document=document,
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _tp1_revision_footer_pdf("Revision No. 01\nFirst Issue: JUL 27/26"),
        [rule],
        document=document,
    )
    missing, missing_suggestions = execute_pdf_rules(
        _tp1_revision_footer_pdf("First Issue: JUL 27/26"),
        [rule],
        document=document,
    )
    not_tp1, not_tp1_suggestions = execute_pdf_rules(
        _tp1_revision_footer_pdf(
            "Revision No. 04\nFirst Issue: JUL 27/26",
            page_type=None,
        ),
        [rule],
        document=document,
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        ("1", "4")
    ]
    assert missing[0].status == "FAIL"
    assert len(missing_suggestions) == 1
    assert missing_suggestions[0].original == ""
    assert missing_suggestions[0].proposed == "Revision No. 04"
    assert missing_suggestions[0].page == 1
    assert missing_suggestions[0].bbox is not None
    assert missing_suggestions[0].bbox[3] <= 760.0
    assert missing_suggestions[0].message == (
        "Règle non satisfaite : numéro de revision non conforme. "
        "Element attendu : Revision No. 04"
    )
    assert not_tp1 == []
    assert not_tp1_suggestions == []


def test_tp1_revision_number_uses_visual_footer_order() -> None:
    parsed = _tp1_revision_footer_pdf(
        "First Issue: JUL 27/26\nRevision No.04"
    )
    first_issue_span = parsed.pages[0].spans[1]
    revision_number_span = parsed.pages[0].spans[2]
    parsed.pages[0].spans[1] = Span(
        text=first_issue_span.text,
        bbox=(40.0, 776.0, 300.0, 786.0),
        page=first_issue_span.page,
        font=first_issue_span.font,
        size=first_issue_span.size,
    )
    parsed.pages[0].spans[2] = Span(
        text=revision_number_span.text,
        bbox=(40.0, 760.0, 300.0, 770.0),
        page=revision_number_span.page,
        font=revision_number_span.font,
        size=revision_number_span.size,
    )

    results, suggestions = execute_pdf_rules(
        parsed,
        [_rule("CUSTOM_TP1_REVISION_NUMBER")],
        document=SimpleNamespace(meta_revision_number="04"),
    )

    assert results[0].status == "PASS"
    assert suggestions == []


def test_tp1_first_issue_date_matches_document_context_value() -> None:
    rule = _rule("CUSTOM_TP1_FIRST_ISSUE_DATE")
    document = SimpleNamespace(meta_first_issue_date="JUL 27/26")

    valid, valid_suggestions = execute_pdf_rules(
        _tp1_revision_footer_pdf("Revision No.04\nFirst Issue: JUL 27/26"),
        [rule],
        document=document,
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _tp1_revision_footer_pdf("Revision No.04\nFirst Issue: JUL 27/25"),
        [rule],
        document=document,
    )
    partial, partial_suggestions = execute_pdf_rules(
        _tp1_revision_footer_pdf("Revision No.04\nFirst issue:"),
        [rule],
        document=document,
    )
    typo, typo_suggestions = execute_pdf_rules(
        _tp1_revision_footer_pdf("Revision No.04\nFisrt iss: JUL 27/26"),
        [rule],
        document=document,
    )
    missing, missing_suggestions = execute_pdf_rules(
        _tp1_revision_footer_pdf("Revision No.04"),
        [rule],
        document=document,
    )
    not_tp1, not_tp1_suggestions = execute_pdf_rules(
        _tp1_revision_footer_pdf(
            "Revision No.04\nFirst Issue: JUL 27/26",
            page_type=None,
        ),
        [rule],
        document=document,
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        ("5", "6")
    ]
    assert partial[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in partial_suggestions] == [
        ("", " JUL 27/26")
    ]
    assert typo[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in typo_suggestions] == [
        ("Fisrt", "First"),
        ("iss", "issue"),
    ]
    assert missing[0].status == "FAIL"
    assert len(missing_suggestions) == 1
    assert missing_suggestions[0].original == ""
    assert missing_suggestions[0].proposed == "First issue: JUL 27/26"
    assert missing_suggestions[0].message == (
        "Règle non satisfaite : date de premiere issue non conforme. "
        "Element attendu : First issue: JUL 27/26"
    )
    assert not_tp1 == []
    assert not_tp1_suggestions == []


def test_highlights_revision_header_matches_mapping() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_REVISION_HEADER")
    document = SimpleNamespace(
        meta_revision_number="04",
        meta_revision_date="JUL 27/26",
    )

    valid = ParsedPdf(
        page_count=1,
        pages=[
            _page_with_footer_lines(
                1, ["Highlights page 1", "REVISION No. 04 DATED JUL 27/26"]
            )
        ],
        full_text="",
        is_signed=False,
    )
    classify_pages(valid, document)
    valid_results, valid_suggestions = execute_pdf_rules(valid, [rule], document=document)

    invalid = ParsedPdf(
        page_count=1,
        pages=[
            _page_with_footer_lines(
                1, ["Highlights page 1", "REVISION No. 05 DATED JUL 27/26"]
            )
        ],
        full_text="",
        is_signed=False,
    )
    classify_pages(invalid, document)
    invalid_results, invalid_suggestions = execute_pdf_rules(
        invalid, [rule], document=document
    )

    missing = ParsedPdf(
        page_count=1,
        pages=[
            _page_with_footer_lines(1, ["Highlights page 1", "Revision date: JUL 27/26"])
        ],
        full_text="",
        is_signed=False,
    )
    classify_pages(missing, document)
    missing_results, _ = execute_pdf_rules(missing, [rule], document=document)

    assert valid.pages[0].page_type == HIGHLIGHTS_FIRST_PAGE_TYPE
    assert valid_results[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid_results[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].original == "REVISION No. 05 DATED JUL 27/26"
    assert invalid_suggestions[0].proposed == "REVISION No. 04 DATED JUL 27/26"
    assert invalid_suggestions[0].bbox == (40.0, 756.0, 300.0, 766.0)
    assert missing_results[0].status == "FAIL"


def test_first_highlights_page_matches_the_tp1_holder_phrase() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_HOLDER")
    tp1_page = ParsedPage(
        page=2,
        page_type=TP1_PAGE_TYPE,
        text="PRESSURE TRANSMITTER\nPART NUMBER",
        spans=[
            Span(
                text="PRESSURE TRANSMITTER",
                bbox=(200.0, 200.0, 450.0, 220.0),
                page=2,
                font="Arial-BoldMT",
                size=19.0,
            ),
            Span(
                text="PART NUMBER",
                bbox=(276.0, 345.0, 375.0, 364.0),
                page=2,
                font="ArialNarrow",
                size=16.0,
            ),
        ],
    )

    valid_page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
        text=(
            "COMPONENT MAINTENANCE MANUAL\n"
            "TO: HOLDER OF PRESSURE TRANSMITTER\n"
            "PNR: 1-879-SB\n"
            "HIGHLIGHTS\n"
            "Revision content"
        ),
        spans=[
            Span(
                text="HIGHLIGHTS",
                bbox=(86.0, 140.0, 180.0, 155.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
            Span(
                text="TO: HOLDER OF PRESSURE TRANSMITTER",
                bbox=(86.0, 180.0, 320.0, 195.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
        ],
    )
    invalid_page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
        text="HIGHLIGHTS\nTO: HOLDER OF OTHER MANUAL",
        spans=[
            Span(
                text="HIGHLIGHTS",
                bbox=(86.0, 140.0, 180.0, 155.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
            Span(
                text="TO: HOLDER OF OTHER MANUAL",
                bbox=(86.0, 180.0, 320.0, 195.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
        ],
    )

    valid, valid_suggestions = execute_pdf_rules(
        ParsedPdf(
            page_count=2,
            pages=[valid_page, tp1_page],
            full_text=valid_page.text + "\n" + tp1_page.text,
            is_signed=False,
        ),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        ParsedPdf(
            page_count=2,
            pages=[invalid_page, tp1_page],
            full_text=invalid_page.text + "\n" + tp1_page.text,
            is_signed=False,
        ),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].original == "TO: HOLDER OF OTHER MANUAL"
    assert invalid_suggestions[0].proposed == "TO: HOLDER OF PRESSURE TRANSMITTER"

    missing_page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
        text="HIGHLIGHTS\nPRESSURE TRANSMITTER\nRevision content",
        spans=[
            Span(
                text="PRESSURE TRANSMITTER",
                bbox=(86.0, 73.9, 212.4, 88.0),
                page=1,
                font="Arial",
                size=12.0,
            ),
            Span(
                text="HIGHLIGHTS",
                bbox=(293.9, 130.4, 359.9, 144.8),
                page=1,
                font="Arial",
                size=12.0,
            ),
        ],
    )
    missing, missing_suggestions = execute_pdf_rules(
        ParsedPdf(
            page_count=2,
            pages=[missing_page, tp1_page],
            full_text=missing_page.text + "\n" + tp1_page.text,
            is_signed=False,
        ),
        [rule],
    )

    assert missing[0].status == "FAIL"
    assert len(missing_suggestions) == 1
    assert missing_suggestions[0].original == ""
    assert missing_suggestions[0].proposed == "TO: HOLDER OF PRESSURE TRANSMITTER"
    assert missing_suggestions[0].bbox == (86.0, 73.9, 212.4, 88.0)


def test_first_highlights_page_contains_the_mapped_ata_number() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_ATA_NUMBER")
    document = SimpleNamespace(
        meta_cmm_number="23-56-25",
        meta_revision_date="JUL 27/26",
    )

    valid_pages = [
        _page_with_footer_lines(
            7,
            [
                "CMM: 23-56-25",
                "JUL 27/26",
                "Highlights Page 1",
                "ATA No 23-56-25",
            ],
        ),
        _page_with_footer_lines(
            8,
            ["CMM: 23-56-25", "JUL 27/26", "Highlights Page 2"],
        ),
    ]
    valid_parsed = ParsedPdf(
        page_count=8,
        pages=valid_pages,
        full_text="\n".join(page.text for page in valid_pages),
        is_signed=False,
    )
    classify_pages(valid_parsed, document)
    valid, valid_suggestions = execute_pdf_rules(
        valid_parsed,
        [rule],
        document=document,
    )

    invalid_page = _page_with_footer_lines(
        7,
        [
            "CMM: 23-56-25",
            "JUL 27/26",
            "Highlights Page 1",
            "ATA No 23-56-24",
        ],
    )
    invalid_parsed = ParsedPdf(
        page_count=7,
        pages=[invalid_page],
        full_text=invalid_page.text,
        is_signed=False,
    )
    classify_pages(invalid_parsed, document)
    invalid, invalid_suggestions = execute_pdf_rules(
        invalid_parsed,
        [rule],
        document=document,
    )

    missing_page = _page_with_footer_lines(
        7,
        ["CMM: 23-56-25", "JUL 27/26", "Highlights Page 1"],
    )
    missing_parsed = ParsedPdf(
        page_count=7,
        pages=[missing_page],
        full_text=missing_page.text,
        is_signed=False,
    )
    classify_pages(missing_parsed, document)
    missing, missing_suggestions = execute_pdf_rules(
        missing_parsed,
        [rule],
        document=document,
    )

    assert valid_pages[0].page_type == HIGHLIGHTS_FIRST_PAGE_TYPE
    assert valid_pages[1].page_type == HIGHLIGHTS_PAGE_TYPE
    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert invalid_suggestions[0].proposed == "ATA No 23-56-25"
    assert missing[0].status == "FAIL"
    assert missing_suggestions[0].proposed == "ATA No 23-56-25"


def test_missing_highlights_ata_number_anchors_the_comment_on_ata_label() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_ATA_NUMBER")
    document = SimpleNamespace(
        meta_cmm_number="23-56-25",
        meta_revision_date="JUL 27/26",
    )
    page = ParsedPage(
        page=7,
        page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
        text="Manual header\n\nATA No  HIGHLIGHTS\nHighlights Page 1",
        spans=[
            Span(
                text="Manual header",
                bbox=(86.0, 80.0, 180.0, 95.0),
                page=7,
                font="Arial",
                size=10.0,
            ),
            Span(
                text="ATA No  ",
                bbox=(86.0, 116.0, 134.0, 131.0),
                page=7,
                font="Arial",
                size=10.0,
            ),
            Span(
                text="HIGHLIGHTS",
                bbox=(86.0, 140.0, 180.0, 155.0),
                page=7,
                font="Arial",
                size=10.0,
            ),
        ],
    )

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=7, pages=[page], full_text=page.text, is_signed=False),
        [rule],
        document=document,
    )

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1
    assert suggestions[0].bbox == (86.0, 116.0, 134.0, 131.0)


def test_highlights_pnr_header_matches_mapping_and_uses_one_header_comment() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    document = SimpleNamespace(meta_pnr_number="1-879-SB")

    page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_PAGE_TYPE,
        text="1-879-SB\nHighlights page 1",
        spans=[
            Span(
                text="1-879-SB",
                bbox=(40.0, 100.0, 180.0, 110.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Highlights page 1",
                bbox=(40.0, 756.0, 220.0, 766.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
        ],
    )
    valid, valid_suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False),
        [rule],
        document=document,
    )

    invalid_page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_PAGE_TYPE,
        text="PNR: 1-878-SB\nHighlights page 1",
        spans=[
            Span(
                text="PNR: 1-878-SB",
                bbox=(40.0, 100.0, 180.0, 110.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Highlights page 1",
                bbox=(40.0, 756.0, 220.0, 766.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
        ],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[invalid_page], full_text=invalid_page.text, is_signed=False),
        [rule],
        document=document,
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].original == "1-878-SB"
    assert invalid_suggestions[0].proposed == "1-879-SB"
    assert invalid_suggestions[0].bbox == (40.0, 100.0, 180.0, 110.0)


def test_highlights_pnr_header_accepts_all_values_or_only_the_first_mapping_value() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    document = SimpleNamespace(
        client_metadata={"meta_pnr_number": ["33140-02", "33140-03"]}
    )

    def build_page(pnr: str) -> ParsedPdf:
        text = f"PNR: {pnr}\nHighlights page 1"
        page = ParsedPage(
            page=1,
            page_type=HIGHLIGHTS_PAGE_TYPE,
            text=text,
            spans=[
                Span(pnr, (40.0, 100.0, 180.0, 110.0), 1, "Arial", 8.0),
                Span(
                    "Highlights page 1",
                    (40.0, 756.0, 220.0, 766.0),
                    1,
                    "Arial",
                    8.0,
                ),
            ],
        )
        return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)

    valid, valid_suggestions = execute_pdf_rules(
        build_page("33140 - 02 and 33140 - 03"), [rule], document=document
    )
    first_only, first_only_suggestions = execute_pdf_rules(
        build_page("33140 - 02"), [rule], document=document
    )
    incomplete, incomplete_suggestions = execute_pdf_rules(
        build_page("33140 - 03"), [rule], document=document
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert first_only[0].status == "PASS"
    assert first_only_suggestions == []
    assert incomplete[0].status == "FAIL"
    assert [
        (item.original, item.proposed) for item in incomplete_suggestions
    ] == [
        ("33140 - 03", "33140-02 and 33140-03")
    ]


def test_highlights_pnr_header_accepts_unseparated_first_mapping_value() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    page = _document_type_header_page("C12438", page_type=HIGHLIGHTS_PAGE_TYPE)
    parsed = ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False)

    results, suggestions = execute_pdf_rules(
        parsed,
        [rule],
        document=SimpleNamespace(
            client_metadata={"meta_pnr_number": ["C12438", "C12438AB01"]}
        ),
    )

    assert results[0].status == "PASS"
    assert suggestions == []


def test_highlights_pnr_header_accepts_shared_series_for_multiple_mapping_values() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    for mapping, header, expected_status in (
        ("64809-505-1\n64809-509-1\n64809-525-1\n64809-526-1", "64809 Series", "PASS"),
        ("123-1, 123-2", "123 series", "PASS"),
        ("1234567-1, 1234567-2", "1234567 SERIES", "PASS"),
        ("64809-505-1, 64809-509-1", "64808 Series", "FAIL"),
        ("64809-505-1, 64809-509-1", "164809 Series", "FAIL"),
        ("64809-505-1, 64810-509-1", "64809 Series", "FAIL"),
        ("64809-505-1", "64809 Series", "FAIL"),
    ):
        page = _document_type_header_page(header, page_type=HIGHLIGHTS_PAGE_TYPE)
        parsed = ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False)

        results, suggestions = execute_pdf_rules(
            parsed, [rule], document=SimpleNamespace(meta_pnr_number=mapping)
        )

        assert results[0].status == expected_status, (mapping, header)
        assert bool(suggestions) is (expected_status == "FAIL"), (mapping, header)


def _document_type_header_page(
    header: str,
    *,
    body: str = "Document body.",
    page_type: str | None = None,
) -> ParsedPage:
    footer = "Page 1"
    return ParsedPage(
        page=1,
        page_type=page_type,
        text=f"{header}\n{body}\n{footer}",
        spans=[
            Span(
                text=header,
                bbox=(40.0, 80.0, 300.0, 95.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
            Span(
                text=body,
                bbox=(40.0, 400.0, 200.0, 415.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
            Span(
                text=footer,
                bbox=(40.0, 760.0, 120.0, 775.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
        ],
    )


def test_non_tp1_headers_require_an_allowed_document_type() -> None:
    rule = _rule("CUSTOM_HEADER_DOCUMENT_TYPE")
    valid, _ = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[_document_type_header_page("COMPONENT MAINTENANCE MANUAL")],
            full_text="",
            is_signed=False,
        ),
        [rule],
    )
    invalid, _ = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[_document_type_header_page("OTHER MANUAL")],
            full_text="",
            is_signed=False,
        ),
        [rule],
    )
    excluded, _ = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[_document_type_header_page("OTHER MANUAL", page_type=TP1_PAGE_TYPE)],
            full_text="",
            is_signed=False,
        ),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert invalid[0].status == "FAIL"
    assert excluded == []


def test_tp1_content_requires_an_allowed_document_type() -> None:
    rule = _rule("CUSTOM_TP1_HEADER_DOCUMENT_TYPE")
    valid, _ = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[
                _document_type_header_page(
                    "TP1 heading",
                    body="OVERHAUL MANUAL",
                    page_type=TP1_PAGE_TYPE,
                )
            ],
            full_text="",
            is_signed=False,
        ),
        [rule],
    )
    invalid, _ = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[
                _document_type_header_page(
                    "OVERHAUL MANUAL",
                    page_type=TP1_PAGE_TYPE,
                )
            ],
            full_text="",
            is_signed=False,
        ),
        [rule],
    )
    excluded, _ = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[_document_type_header_page("OTHER MANUAL")],
            full_text="",
            is_signed=False,
        ),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert invalid[0].status == "FAIL"
    assert excluded == []


def test_highlights_document_type_must_precede_the_ata_number() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_DOCUMENT_TYPE")
    invalid_page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
        text="ATA No 23-56-25\nOVERHAUL MANUAL\nHighlights Page 1",
    )
    later_page = ParsedPage(
        page=2,
        page_type=HIGHLIGHTS_PAGE_TYPE,
        text="Highlights Page 2",
    )

    for document_type in DOCUMENT_TYPES:
        valid_page = ParsedPage(
            page=1,
            page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
            text=f"{document_type}\nATA No 23-56-25\nHighlights Page 1",
        )
        valid, _ = execute_pdf_rules(
            ParsedPdf(
                page_count=1,
                pages=[valid_page],
                full_text=valid_page.text,
                is_signed=False,
            ),
            [rule],
        )
        assert valid[0].status == "PASS", document_type
    invalid, _ = execute_pdf_rules(
        ParsedPdf(
            page_count=1,
            pages=[invalid_page],
            full_text=invalid_page.text,
            is_signed=False,
        ),
        [rule],
    )
    later, _ = execute_pdf_rules(
        ParsedPdf(
            page_count=2,
            pages=[later_page],
            full_text=later_page.text,
            is_signed=False,
        ),
        [rule],
    )

    assert invalid[0].status == "FAIL"
    assert later == []

def test_highlights_document_type_accepts_illustrated_parts_list_suffix() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_DOCUMENT_TYPE")
    text = (
        "COMPONENT MAINTENANCE MANUAL with Illustrated Parts List\n"
        "ATA No 21-33-13\n"
        "Highlights Page 1"
    )
    page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
        text=text,
    )

    results, _ = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False),
        [rule],
    )

    assert results[0].status == "PASS"


def test_highlights_legend_must_be_the_last_body_line_before_the_footer() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_LEGEND_FOOTER")

    def build_pdf(*, has_intervening_line: bool) -> ParsedPdf:
        lines = [
            PdfLine(
                "Chapter / Section Revision Status",
                (40.0, 680.0, 520.0, 692.0),
                0,
                0,
            ),
            PdfLine(
                "N: New - D: Deleted - R: Revised - U: Unchanged",
                (40.0, 710.0, 520.0, 722.0),
                0,
                1,
            ),
        ]
        if has_intervening_line:
            lines.append(
                PdfLine("Extra body line", (40.0, 730.0, 520.0, 742.0), 0, 2)
            )
        lines.extend(
            [
                PdfLine("THALES AVS FRANCE SAS", (240.0, 756.0, 400.0, 766.0), 1, 0),
                PdfLine("Highlights Page 1", (40.0, 756.0, 180.0, 766.0), 1, 1),
                PdfLine("JUL 27/26", (40.0, 772.0, 120.0, 782.0), 1, 2),
            ]
        )
        text = "\n".join(line.text for line in lines)
        page = ParsedPage(
            page=1,
            text=text,
            page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
            lines=lines,
            page_height=792.0,
        )
        return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)

    valid, _ = execute_pdf_rules(build_pdf(has_intervening_line=False), [rule])
    invalid, _ = execute_pdf_rules(build_pdf(has_intervening_line=True), [rule])

    assert valid[0].status == "PASS"
    assert invalid[0].status == "FAIL"
    assert invalid[0].evidence.observed_value == "Extra body line"


def test_highlights_document_type_does_not_use_the_centered_page_header() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_DOCUMENT_TYPE")
    page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
        text=(
            "OVERHAUL MANUAL\n"
            "1-879-SB\n"
            "PRESSURE TRANSMITTER\n"
            "PNR: 1-879-SB\n"
            "MANUAL with Illustrated Parts List\n"
            "ATA No\n"
            "HIGHLIGHTS"
        ),
        spans=[
            Span(
                text="OVERHAUL MANUAL",
                bbox=(280.0, 45.0, 375.0, 60.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
            Span(
                text="MANUAL with Illustrated Parts List",
                bbox=(86.0, 160.0, 300.0, 175.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
            Span(
                text="ATA No",
                bbox=(86.0, 180.0, 134.0, 195.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
        ],
    )

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False),
        [rule],
    )

    assert results[0].status == "FAIL"
    assert [
        (suggestion.original, suggestion.proposed)
        for suggestion in suggestions
    ] == [("MANUAL with Illustrated Parts List", "OVERHAUL MANUAL")]
    assert suggestions[0].bbox == (86.0, 160.0, 300.0, 175.0)


def test_pnr_header_reports_each_invalid_page() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    document = SimpleNamespace(meta_pnr_number="1-879-SB")

    page_data = [
        (1, HIGHLIGHTS_FIRST_PAGE_TYPE, "1-878-SB"),
        (2, HIGHLIGHTS_PAGE_TYPE, "1-877-SB"),
        (3, HIGHLIGHTS_PAGE_TYPE, "1-876-SB"),
    ]
    pages = [
        ParsedPage(
            page=page_number,
            page_type=page_type,
            text=f"PNR: {pnr}\nHighlights page {page_number}",
            spans=[
                Span(
                    text=f"PNR: {pnr}",
                    bbox=(40.0, 100.0, 180.0, 110.0),
                    page=page_number,
                    font="Arial",
                    size=8.0,
                ),
                Span(
                    text=f"Highlights page {page_number}",
                    bbox=(40.0, 756.0, 220.0, 766.0),
                    page=page_number,
                    font="Arial",
                    size=8.0,
                ),
            ],
        )
        for page_number, page_type, pnr in page_data
    ]

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=3, pages=pages, full_text="\n".join(page.text for page in pages), is_signed=False),
        [rule],
        document=document,
    )

    assert results[0].status == "FAIL"
    assert [(suggestion.page, suggestion.original) for suggestion in suggestions] == [
        (1, "1-878-SB"),
        (2, "1-877-SB"),
        (3, "1-876-SB"),
    ]


def test_pnr_header_reports_each_invalid_occurrence() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    document = SimpleNamespace(meta_pnr_number="1-879-SB")
    page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_PAGE_TYPE,
        text="PNR: 1-878-SB | PNR: 1-877-SB\nHighlights page 1",
        spans=[
            Span(
            text="PNR: 1-878-SB | PNR: 1-877-SB",
                bbox=(40.0, 100.0, 300.0, 110.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Highlights page 1",
                bbox=(40.0, 756.0, 220.0, 766.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
        ],
    )

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False),
        [rule],
        document=document,
    )

    assert results[0].status == "FAIL"
    assert [suggestion.original for suggestion in suggestions] == [
        "1-878-SB",
        "1-877-SB",
    ]


def test_pnr_header_is_not_checked_outside_highlights_pages() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    document = SimpleNamespace(meta_pnr_number="1-879-SB")
    tp1_page = ParsedPage(
        page=1,
        page_type=TP1_PAGE_TYPE,
        text="PNR: 1-878-SB\nTP1 page 1",
        spans=[
            Span(
                text="PNR: 1-878-SB",
                bbox=(40.0, 100.0, 180.0, 110.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="TP1 page 1",
                bbox=(40.0, 756.0, 180.0, 766.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
        ],
    )
    regular_page = ParsedPage(
        page=2,
        page_type=None,
        text="PNR: 1-878-SB\nRegular page 2",
        spans=[
            Span(
                text="PNR: 1-878-SB",
                bbox=(40.0, 100.0, 180.0, 110.0),
                page=2,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Regular page 2",
                bbox=(40.0, 756.0, 180.0, 766.0),
                page=2,
                font="Arial",
                size=8.0,
            ),
        ],
    )

    tp1_results, tp1_suggestions = execute_pdf_rules(
        ParsedPdf(1, [tp1_page], tp1_page.text, False),
        [rule],
        document=document,
    )
    regular_results, regular_suggestions = execute_pdf_rules(
        ParsedPdf(1, [regular_page], regular_page.text, False),
        [rule],
        document=document,
    )

    assert tp1_results == []
    assert tp1_suggestions == []
    assert regular_results == []
    assert regular_suggestions == []


def test_pnr_in_page_is_checked_when_present_but_not_required() -> None:
    rule = _rule("CUSTOM_TP1_PNR_PAGE_VALUE")
    document = SimpleNamespace(meta_pnr_number="1-879-SB")

    valid_page = ParsedPage(
        page=1,
        page_type=TP1_PAGE_TYPE,
        text="PNR: 1-878-SB\nDocument body without a PNR.",
        spans=[
            Span(
                text="PNR: 1-878-SB",
                bbox=(40.0, 100.0, 300.0, 110.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Document body without a PNR.",
                bbox=(40.0, 400.0, 300.0, 410.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Footer",
                bbox=(40.0, 760.0, 100.0, 770.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
        ],
    )
    invalid_page = ParsedPage(
        page=2,
        page_type=TP1_PAGE_TYPE,
        text="PNR: 1-878-SB\nDocument body\n1-878-SB",
        spans=[
            Span(
                text="PNR: 1-878-SB",
                bbox=(40.0, 100.0, 300.0, 110.0),
                page=2,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Document body",
                bbox=(40.0, 400.0, 180.0, 410.0),
                page=2,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="1-878-SB",
                bbox=(40.0, 420.0, 120.0, 430.0),
                page=2,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Footer",
                bbox=(40.0, 760.0, 100.0, 770.0),
                page=2,
                font="Arial",
                size=8.0,
            ),
        ],
    )
    generic_page = ParsedPage(
        page=3,
        text="Generic page body - 1-878-SB",
        spans=[
            Span(
                text="Generic page body - 1-878-SB",
                bbox=(40.0, 400.0, 300.0, 410.0),
                page=3,
                font="Arial",
                size=8.0,
            )
        ],
    )

    valid, valid_suggestions = execute_pdf_rules(
        ParsedPdf(1, [valid_page], valid_page.text, False),
        [rule],
        document=document,
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        ParsedPdf(1, [invalid_page], invalid_page.text, False),
        [rule],
        document=document,
    )
    ignored, ignored_suggestions = execute_pdf_rules(
        ParsedPdf(1, [generic_page], generic_page.text, False),
        [rule],
        document=document,
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        ("1-878-SB", "1-879-SB")
    ]
    assert ignored == []
    assert ignored_suggestions == []


def test_tp1_pnr_page_value_uses_mapping_without_a_fixed_format() -> None:
    rule = _rule("CUSTOM_TP1_PNR_PAGE_VALUE")
    pnr_values = [
        "5306-255-00-09",
        "5306-265-00-10",
        "5306-266-20-10",
        "5306-266-20-11",
        "5306-261-00-11",
    ]
    document = SimpleNamespace(client_metadata={"meta_pnr_number": pnr_values})

    def build_pdf(values: list[str]) -> ParsedPdf:
        spans = [
            Span("TP1 header", (40.0, 100.0, 120.0, 110.0), 1, "Arial", 8.0),
            Span(
                "OIL TEMPERATURE INDICATOR",
                (40.0, 250.0, 300.0, 265.0),
                1,
                "Arial",
                10.0,
            ),
        ]
        for index, value in enumerate(values):
            y = 300.0 + index * 22.0
            spans.append(
                Span(value, (40.0, y, 220.0, y + 12.0), 1, "Arial", 10.0)
            )
        spans.extend(
            [
                Span(
                    "COMPONENT MAINTENANCE MANUAL",
                    (40.0, 500.0, 300.0, 515.0),
                    1,
                    "Arial",
                    10.0,
                ),
                Span("Footer", (40.0, 760.0, 100.0, 770.0), 1, "Arial", 8.0),
            ]
        )
        text = "\n".join(span.text for span in spans)
        page = ParsedPage(page=1, page_type=TP1_PAGE_TYPE, text=text, spans=spans)
        return ParsedPdf(1, [page], text, False)

    valid, valid_suggestions = execute_pdf_rules(
        build_pdf(pnr_values), [rule], document=document
    )
    incorrect_values = ["5306-255-00-11", *pnr_values[1:]]
    invalid, invalid_suggestions = execute_pdf_rules(
        build_pdf(incorrect_values), [rule], document=document
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert invalid[0].evidence.observed_value == "5306-255-00-11"
    assert [
        (item.original, item.proposed) for item in invalid_suggestions
    ] == [("5306-255-00-11", "5306-255-00-09")]


def test_highlights_pnr_label_is_checked_without_rechecking_the_header() -> None:
    rule = _rule("CUSTOM_PNR_PAGE_VALUE")
    document = SimpleNamespace(meta_pnr_number="1-879-SB")

    valid_page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_PAGE_TYPE,
        text="1-878-SB\nPNR: 1-879-SB\nHighlights page 1",
        spans=[
            Span(
                text="1-878-SB",
                bbox=(40.0, 100.0, 180.0, 110.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="PNR: 1-879-SB",
                bbox=(40.0, 300.0, 180.0, 310.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Highlights page 1",
                bbox=(40.0, 756.0, 220.0, 766.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
        ],
    )
    invalid_page = ParsedPage(
        page=1,
        page_type=HIGHLIGHTS_PAGE_TYPE,
        text="1-878-SB\nPNR: 1-878-SB\nHighlights page 1",
        spans=[
            Span(
                text="1-878-SB",
                bbox=(40.0, 100.0, 180.0, 110.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="PNR: 1-878-SB",
                bbox=(40.0, 300.0, 180.0, 310.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Highlights page 1",
                bbox=(40.0, 756.0, 220.0, 766.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
        ],
    )

    valid, valid_suggestions = execute_pdf_rules(
        ParsedPdf(1, [valid_page], valid_page.text, False),
        [rule],
        document=document,
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        ParsedPdf(1, [invalid_page], invalid_page.text, False),
        [rule],
        document=document,
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        ("1-878-SB", "1-879-SB")
    ]


def _page_with_footer_lines(page_number: int, footer_lines: list[str]) -> ParsedPage:
    body = f"Page body {page_number}."
    spans = [
        Span(
            text=body,
            bbox=(40.0, 100.0, 200.0, 120.0),
            page=page_number,
            font="Arial",
            size=10.0,
        )
    ]
    for index, line in enumerate(footer_lines):
        top = 740.0 + index * 16.0
        spans.append(
            Span(
                text=line,
                bbox=(40.0, top, 300.0, top + 10.0),
                page=page_number,
                font="Arial",
                size=8.0,
            )
        )
    return ParsedPage(
        page=page_number,
        text="\n".join([body, *footer_lines]),
        spans=spans,
    )


def test_tp1_page_type_is_read_from_anywhere_in_the_footer_band() -> None:
    # Les vrais pieds de page intercalent CMM/date/TP1 (colonne etroite) avec
    # un paragraphe copyright multi-lignes (colonne large) : le regroupement
    # par position Y de `_footer_lines` ne place quasiment jamais le marqueur
    # TP1 juste apres la ligne d'ancrage, d'ou la detection par co-presence.
    parsed = ParsedPdf(
        page_count=2,
        pages=[
            _page_with_footer_lines(1, ["Revision: JUL 27/26", "TP1"]),
            _page_with_footer_lines(2, ["Revision: JUL 27/26", "Other line", "TP1"]),
        ],
        full_text="",
        is_signed=False,
    )

    page_types = identify_tp1_pages(parsed, "JUL 27/26")

    assert page_types == {"1": "TP1", "2": "TP1"}
    assert parsed.pages[0].page_type == TP1_PAGE_TYPE
    assert parsed.pages[1].page_type == TP1_PAGE_TYPE


def test_repair_testing_storage_page_types_require_standalone_headings() -> None:
    parsed = ParsedPdf(
        page_count=5,
        pages=[
            ParsedPage(page=1, text="REPAIR\nNOTE\nPressure:"),
            ParsedPage(page=2, text="TESTING\nNOTE\nTemperature:"),
            ParsedPage(page=3, text="STORAGE\nNOTE\nPressure:"),
            ParsedPage(
                page=4,
                text=(
                    "NOTE\nRelative humidity: Refer to Standard Practices "
                    "Manual ATA No. 20-02-00, F9111CMON-A-20-02-00-00A-812A-A "
                    "- Storage and Transportation of Assemblies."
                ),
            ),
        ],
        full_text="",
        is_signed=False,
    )

    page_types = identify_note_pages(parsed)

    assert page_types == {
        "1": REPAIR_PAGE_TYPE,
        "2": TESTING_PAGE_TYPE,
        "3": STORAGE_PAGE_TYPE,
        "4": None,
    }


def test_note_page_classifier_does_not_misclassify_contents_or_override_highlights() -> None:
    parsed = ParsedPdf(
        page_count=4,
        pages=[
            ParsedPage(
                page=1,
                text="Highlights Page 1\nRepair\nTesting\nStorage\nPRESSURE",
            ),
            ParsedPage(
                page=2,
                text="Highlights Page 2\nRepair\nTesting\nStorage",
                page_type=HIGHLIGHTS_PAGE_TYPE,
            ),
            ParsedPage(
                page=3,
                text="LIST OF EFFECTIVE PAGES\nSUBJECT\nPAGE\nDATE\nStorage\n901",
            ),
            ParsedPage(
                page=4,
                text="TABLE OF CONTENTS\nStorage\n901",
            ),
            ParsedPage(
                page=5,
                text="STORAGE INSTRUCTIONS\n1. STORAGE\nNOTE: During storage operations",
            ),
        ],
        full_text="",
        is_signed=False,
    )

    page_types = identify_note_pages(parsed)

    assert page_types == {
        "1": None,
        "2": HIGHLIGHTS_PAGE_TYPE,
        "3": None,
        "4": None,
        "5": "STORAGE",
    }


def test_introduction_page_classifier_uses_the_standalone_heading() -> None:
    parsed = ParsedPdf(
        page_count=2,
        pages=[
            ParsedPage(page=1, text="INTRODUCTION\nShop Verification:"),
            ParsedPage(page=2, text="Introduction is mentioned in body text."),
            ParsedPage(page=3, text="TABLE OF CONTENTS\nINTRODUCTION\nINTRO 1"),
        ],
        full_text="",
        is_signed=False,
    )

    page_types = identify_introduction_pages(parsed)

    assert page_types == {"1": INTRODUCTION_PAGE_TYPE, "2": None, "3": None}


def test_shop_verification_changes_with_the_mapping_manufacturer() -> None:
    rule = _rule("CUSTOM_INTRODUCTION_SHOP_VERIFICATION")
    airbus_text = shop_verification_text(SimpleNamespace(meta_manufacturer="Airbus"))
    boeing_text = shop_verification_text(SimpleNamespace(meta_manufacturer="Boeing"))

    airbus_results, airbus_suggestions = execute_pdf_rules(
        _note_page_pdf(airbus_text, INTRODUCTION_PAGE_TYPE),
        [rule],
        document=SimpleNamespace(meta_manufacturer="Airbus"),
    )
    boeing_results, boeing_suggestions = execute_pdf_rules(
        _note_page_pdf(boeing_text, INTRODUCTION_PAGE_TYPE),
        [rule],
        document=SimpleNamespace(meta_manufacturer="Boeing"),
    )
    invalid_results, invalid_suggestions = execute_pdf_rules(
        _note_page_pdf(boeing_text, INTRODUCTION_PAGE_TYPE),
        [rule],
        document=SimpleNamespace(meta_manufacturer="Airbus"),
    )

    assert airbus_results[0].status == "PASS"
    assert airbus_suggestions == []
    assert boeing_results[0].status == "PASS"
    assert boeing_suggestions == []
    assert invalid_results[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].page == 1
    assert invalid_suggestions[0].proposed == airbus_text
    assert "Airbus" in invalid_suggestions[0].message


def test_deleted_highlights_require_chapter_or_page_deleted_description() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_DELETION_DESCRIPTION")

    for description in ("Chapter deleted", "Page deleted"):
        results, suggestions = execute_pdf_rules(
            _highlights_structure_pdf(
                [("Repair", "", ""), ("Pages 601 to 602", "D", description)]
            ),
            [rule],
        )
        assert results[0].status == "PASS"
        assert suggestions == []

    results, suggestions = execute_pdf_rules(
        _highlights_structure_pdf(
            [("Repair", "", ""), ("Pages 601 to 602", "D", "Removed from the manual")]
        ),
        [rule],
    )

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1
    assert suggestions[0].page == 1
    assert suggestions[0].bbox[0] >= 300.0


@pytest.mark.parametrize(
    "chapter",
    [
        "Illustrated Parts List",
        "Illustrated Part Lis",
        "illustrated part list",
        "Illustarted Parts List",
        "IllustratedPartsList",
    ],
)
def test_revised_highlights_require_description_with_illustrated_parts_list_exception(
    chapter: str,
) -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_REVISED_DESCRIPTION")
    ordinary_missing, missing_suggestions = execute_pdf_rules(
        _highlights_structure_pdf(
            [("Repair", "", ""), ("Page 601", "R", "")]
        ),
        [rule],
    )
    ordinary_present, present_suggestions = execute_pdf_rules(
        _highlights_structure_pdf(
            [("Repair", "", ""), ("Page 601", "R", "Corrected assembly instruction")]
        ),
        [rule],
    )
    illustrated_list, illustrated_suggestions = execute_pdf_rules(
        _highlights_structure_pdf(
            [
                (chapter, "", "Revised to reflect this revision."),
                ("INTRO 1101 Page 1 to INTRO Page 2", "R", ""),
                ("NI/NUM 1101 Page 1", "R", ""),
            ]
        ),
        [rule],
    )
    illustrated_missing, illustrated_missing_suggestions = execute_pdf_rules(
        _highlights_structure_pdf(
            [
                (chapter, "", ""),
                ("INTRO 1101 Page 1 to INTRO Page 2", "R", ""),
                ("NI/NUM 1101 Page 1", "R", ""),
            ]
        ),
        [rule],
    )

    assert ordinary_missing[0].status == "FAIL"
    assert len(missing_suggestions) == 1
    assert ordinary_present[0].status == "PASS"
    assert present_suggestions == []
    assert illustrated_list[0].status == "PASS"
    assert illustrated_suggestions == []
    assert illustrated_missing[0].status == "FAIL"
    assert len(illustrated_missing_suggestions) == 1


@pytest.mark.parametrize(
    "description",
    [
        "Environmental condition and minor technical correction.",
        "Environmentel conditions and minor technical correction.",
    ],
)
def test_highlights_description_checks_environmental_conditions_spelling(
    description: str,
) -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_ENVIRONMENTAL_CONDITIONS")
    valid, valid_suggestions = execute_pdf_rules(
        _highlights_structure_pdf(
            [("Page 601", "R", "Environmental conditions and correction.")]
        ),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _highlights_structure_pdf([("Page 601", "N", description)]),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].original == description.split(" and ")[0]
    assert invalid_suggestions[0].proposed == "Environmental conditions"
    assert invalid_suggestions[0].bbox is not None


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


def test_chapter_number_sequence_continues_across_pages_and_detects_gaps() -> None:
    rule = _rule("CUSTOM_CHAPTER_NUMBER_SEQUENCE")
    valid, valid_suggestions = execute_pdf_rules(
        _numbered_chapter_pdf(
            [
                ("501", ["1. INFORMATION", "2. MECHANICAL ASSEMBLY"]),
                ("502", ["3. CHECKING AND ADJUSTMENTS"]),
            ]
        ),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _numbered_chapter_pdf(
            [("701", ["1. INFORMATION"]), ("702", ["3. LEAK TESTS"])]
        ),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].page == 2
    assert invalid_suggestions[0].proposed == "2. LEAK TESTS"


def test_chapter_sequence_counts_unformatted_heading_on_previous_page() -> None:
    rule = _rule("CUSTOM_CHAPTER_NUMBER_SEQUENCE")
    full_document = _numbered_chapter_pdf(
        [
            ("300", ["1. General", "A. Checks before Disassembly"]),
            ("301", ["2. Procedure"]),
        ]
    )
    full_document.pages[0].is_modified = False
    full_document.pages[1].is_modified = True

    results, suggestions = execute_pdf_rules(
        filter_pdf_pages(full_document, [2]),
        [rule],
    )

    assert results[0].status == "PASS"
    assert suggestions == []


@pytest.mark.parametrize("current_heading, expected_status", [("2. Procedure", "PASS"), ("3. Procedure", "FAIL")])
def test_chapter_sequence_counts_previous_page_with_legacy_copyright(
    current_heading: str, expected_status: str,
) -> None:
    full_document = _numbered_chapter_pdf(
        [("301", ["1. General"]), ("302", [current_heading])]
    )
    previous_page = full_document.pages[0]
    previous_page.spans[-3].text = (
        "\u00a9THALES AVIONICS SAS. This document and any data included"
    )
    previous_page.is_modified = False
    full_document.pages[1].is_modified = True

    results, suggestions = execute_pdf_rules(
        filter_pdf_pages(full_document, [2]),
        [_rule("CUSTOM_CHAPTER_NUMBER_SEQUENCE")],
    )

    assert results[0].status == expected_status
    assert [suggestion.proposed for suggestion in suggestions] == (
        [] if expected_status == "PASS" else ["2. Procedure"]
    )


def test_chapter_sequence_recognizes_heading_without_extracted_span_space() -> None:
    rule = _rule("CUSTOM_CHAPTER_NUMBER_SEQUENCE")
    full_document = _numbered_chapter_pdf(
        [
            ("300", ["1.General"]),
            ("301", ["2. Procedure"]),
        ]
    )
    full_document.pages[0].is_modified = False
    full_document.pages[1].is_modified = True

    results, suggestions = execute_pdf_rules(
        filter_pdf_pages(full_document, [2]),
        [rule],
    )

    assert results[0].status == "PASS"
    assert suggestions == []


def test_chapter_number_sequence_accepts_sentence_case_and_figure_titles() -> None:
    rule = _rule("CUSTOM_CHAPTER_NUMBER_SEQUENCE")
    results, suggestions = execute_pdf_rules(
        _numbered_chapter_pdf(
            [
                ("701", ["1. Assembly (Figure 301)", "2. Storage"]),
                (
                    "901",
                    ["1. Special tools", "2. Standard tools", "3. Consumables"],
                ),
            ]
        ),
        [rule],
    )

    assert results[0].status == "PASS"
    assert suggestions == []


def test_chapter_number_sequence_ignores_numbered_prose() -> None:
    rule = _rule("CUSTOM_CHAPTER_NUMBER_SEQUENCE")
    results, suggestions = execute_pdf_rules(
        _numbered_chapter_pdf(
            [("501", ["1. Replace the seal immediately."])]
        ),
        [rule],
    )

    assert results[0].status == "INCONCLUSIVE"
    assert suggestions == []


def test_chapter_sequence_uses_full_document_for_a_single_page_analysis() -> None:
    rule = _rule("CUSTOM_CHAPTER_NUMBER_SEQUENCE")
    valid_full = _numbered_chapter_pdf(
        [("701", ["1. INFORMATION"]), ("702", ["2. LEAK TESTS"])]
    )
    valid_full.pages[0].is_modified = False
    valid_full.pages[1].is_modified = True
    valid_results, valid_suggestions = execute_pdf_rules(
        filter_pdf_pages(valid_full, [2]),
        [rule],
    )

    full = _numbered_chapter_pdf(
        [("701", ["1. INFORMATION"]), ("702", ["3. LEAK TESTS"])]
    )
    full.pages[0].is_modified = False
    full.pages[1].is_modified = True
    partial = filter_pdf_pages(full, [2])

    results, suggestions = execute_pdf_rules(partial, [rule])

    assert valid_results[0].status == "PASS"
    assert valid_suggestions == []
    assert results[0].status == "FAIL"
    assert suggestions[0].page == 2
    assert suggestions[0].proposed == "2. LEAK TESTS"


def test_pdf_bookmark_title_must_appear_on_its_destination_page() -> None:
    rule = _rule("CUSTOM_PDF_BOOKMARK_TITLE_MATCH")
    pages = [
        ParsedPage(page=1, text="INTRODUCTION"),
        ParsedPage(page=2, text="REPAIR PROCEDURE"),
    ]
    valid = ParsedPdf(
        page_count=2,
        pages=pages,
        full_text="INTRODUCTION\nREPAIR PROCEDURE",
        is_signed=False,
        bookmarks=[
            PdfBookmark(title="INTRODUCTION", page=1),
            PdfBookmark(title="REPAIR PROCEDURE", page=2),
        ],
    )
    invalid = ParsedPdf(
        page_count=2,
        pages=pages,
        full_text="INTRODUCTION\nREPAIR PROCEDURE",
        is_signed=False,
        bookmarks=[PdfBookmark(title="REPAIR PROCEDURE", page=1)],
    )

    valid_results, valid_suggestions = execute_pdf_rules(valid, [rule])
    invalid_results, invalid_suggestions = execute_pdf_rules(invalid, [rule])

    assert valid_results[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid_results[0].status == "FAIL"
    assert [(item.page, item.original, item.proposed) for item in invalid_suggestions] == [
        (1, "REPAIR PROCEDURE", "")
    ]


@pytest.mark.parametrize(
    ("bookmark_title", "page_title", "expected_status"),
    [
        ("LIST OF EFFECTIVE PAGES", "LIST OF EFFECTIVES PAGES", "PASS"),
        ("LIST EFFECTIVE PAGES", "LIST OF EFFECTIVES PAGES", "PASS"),
        ("LIST OF EFFECTIVE PAGES", "LIST OF EFECTIVE PAGES", "PASS"),
        ("Illustrated Parts List", "ILLUSTRATED PART LIS", "PASS"),
        ("REPAIR PROCEDURE", "REPAIR PROCEDURES", "PASS"),
        ("REPAIR PROCEDURE", "INTRODUCTION", "FAIL"),
        ("REPAIR PROCEDURE 101", "REPAIR PROCEDURE 102", "FAIL"),
        ("CHECK", "CHEEK", "FAIL"),
    ],
)
def test_pdf_bookmark_tolerates_small_title_typos_but_not_wrong_destinations(
    bookmark_title: str, page_title: str, expected_status: str,
) -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text=page_title)],
        full_text=page_title,
        is_signed=False,
        bookmarks=[PdfBookmark(title=bookmark_title, page=1)],
    )

    results, suggestions = execute_pdf_rules(parsed, [_rule("CUSTOM_PDF_BOOKMARK_TITLE_MATCH")])

    assert results[0].status == expected_status
    assert bool(suggestions) is (expected_status == "FAIL")


def test_pdf_bookmark_does_not_match_a_repeated_page_header() -> None:
    header = "COMPONENT MAINTENANCE MANUAL"
    pages = [
        ParsedPage(
            page=1,
            text=f"{header} 79-30-02 PAGE 1\nLIST OF EFFECTIVE PAGES\nINTRODUCTION",
            lines=[
                PdfLine(f"{header} 79-30-02 PAGE 1", (30.0, 18.0, 400.0, 30.0), 0, 0),
                PdfLine("LIST OF EFFECTIVE PAGES", (70.0, 85.0, 280.0, 105.0), 1, 0),
                PdfLine("INTRODUCTION", (70.0, 180.0, 230.0, 200.0), 1, 0),
            ],
            spans=[
                Span(f"{header} 79-30-02 PAGE 1", (30.0, 18.0, 400.0, 30.0), 1, "Arial", 8.0),
                Span("LIST OF EFFECTIVE PAGES", (70.0, 85.0, 280.0, 105.0), 1, "Arial-Bold", 18.0),
                Span("INTRODUCTION", (70.0, 180.0, 230.0, 200.0), 1, "Arial", 12.0),
            ],
            page_height=792.0,
        ),
        ParsedPage(
            page=2,
            text=f"{header} 79-30-02 PAGE 2\nREPAIR PROCEDURE",
            lines=[
                PdfLine(f"{header} 79-30-02 PAGE 2", (30.0, 18.0, 400.0, 30.0), 0, 0),
                PdfLine("REPAIR PROCEDURE", (70.0, 180.0, 250.0, 200.0), 1, 0),
            ],
            spans=[
                Span(f"{header} 79-30-02 PAGE 2", (30.0, 18.0, 400.0, 30.0), 2, "Arial", 8.0),
                Span("REPAIR PROCEDURE", (70.0, 180.0, 250.0, 200.0), 2, "Arial", 12.0),
            ],
            page_height=792.0,
        ),
    ]
    parsed = ParsedPdf(
        page_count=2,
        pages=pages,
        full_text="\n".join(page.text for page in pages),
        is_signed=False,
        bookmarks=[
            PdfBookmark(title=header, page=1),
            PdfBookmark(title="LIST OF EFFECTIVE PAGE", page=1),
            PdfBookmark(title="INTRODUCTION", page=1),
        ],
    )

    results, suggestions = execute_pdf_rules(parsed, [_rule("CUSTOM_PDF_BOOKMARK_TITLE_MATCH")])

    assert results[0].status == "FAIL"
    assert [(item.original, item.page) for item in suggestions] == [(header, 1)]


def test_pdf_bookmark_typo_does_not_match_running_header() -> None:
    header = "COMPONENT MAINTENANCE MANUAL"
    page = ParsedPage(
        page=1,
        text=f"{header}\nREPAIR PROCEDURE",
        lines=[
            PdfLine(header, (30.0, 18.0, 400.0, 30.0), 0, 0),
            PdfLine("REPAIR PROCEDURE", (70.0, 180.0, 250.0, 200.0), 1, 0),
        ],
        spans=[
            Span(header, (30.0, 18.0, 400.0, 30.0), 1, "Arial", 8.0),
            Span("REPAIR PROCEDURE", (70.0, 180.0, 250.0, 200.0), 1, "Arial", 12.0),
        ],
        page_height=792.0,
    )
    parsed = ParsedPdf(
        page_count=1,
        pages=[page],
        full_text=page.text,
        is_signed=False,
        bookmarks=[PdfBookmark(title="COMPONENT MAINTENACE MANUAL", page=1)],
    )

    results, suggestions = execute_pdf_rules(parsed, [_rule("CUSTOM_PDF_BOOKMARK_TITLE_MATCH")])

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1


def test_pdf_bookmark_inconclusive_pages_survive_modified_only_filtering() -> None:
    rule = _rule("CUSTOM_PDF_BOOKMARK_TITLE_MATCH")
    parsed = ParsedPdf(
        page_count=3,
        pages=[
            ParsedPage(page=1, text="COMPONENT MAINTENANCE MANUAL"),
            ParsedPage(page=2, text="REPAIR PROCEDURE"),
            ParsedPage(page=3, text="", has_text_layer=False),
        ],
        full_text="COMPONENT MAINTENANCE MANUAL\nREPAIR PROCEDURE\n",
        is_signed=False,
        bookmarks=[
            PdfBookmark(title="TITLE PAGE", page=1),
            PdfBookmark(title="WRONG TITLE", page=2),
            PdfBookmark(title="DISASSEMBLY", page=3),
        ],
    )

    scoped = filter_pdf_pages(parsed, [1, 2])
    results, suggestions = execute_pdf_rules(scoped, [rule])

    assert results[0].status == "FAIL"
    assert results[0].inconclusive_pages == ["1", "3"]
    assert [(item.page, item.original) for item in suggestions] == [(2, "WRONG TITLE")]


def test_list_of_materials_code_rule_only_checks_the_code_column() -> None:
    rule = _rule("CUSTOM_LIST_OF_MATERIALS_CODE_NO_PARENTHESES")
    parsed = _list_materials_code_pdf(
        [("Red paint (red)", "CODE-01", "Supplier (FSCM)")]
    )

    valid, valid_suggestions = execute_pdf_rules(parsed, [rule])

    assert valid[0].status == "PASS"
    assert valid_suggestions == []

    parsed = _list_materials_code_pdf(
        [("Red paint", "(pa-pa-024)", "Supplier (FSCM)")]
    )
    invalid, invalid_suggestions = execute_pdf_rules(parsed, [rule])

    assert invalid[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].original == "(pa-pa-024)"
    assert invalid_suggestions[0].proposed == "pa-pa-024"


def test_list_of_materials_code_must_not_contain_uppercase_letters() -> None:
    rule = _rule("CUSTOM_LIST_OF_MATERIALS_CODE_LOWERCASE")
    valid, valid_suggestions = execute_pdf_rules(
        _list_materials_code_pdf(
            [("RED PAINT", "pa-pa-024", "SUPPLIER ABC")]
        ),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _list_materials_code_pdf(
            [("RED PAINT", "PA-PA-024", "SUPPLIER ABC")]
        ),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        ("PA-PA-024", "pa-pa-024")
    ]


def test_list_of_materials_supplier_requires_fscm_in_parentheses() -> None:
    rule = _rule("CUSTOM_LIST_OF_MATERIALS_SUPPLIER_FSCM")
    valid, valid_suggestions = execute_pdf_rules(
        _list_materials_code_pdf(
            [
                ("RED PAINT", "pa-pa-024", "ACME AEROSPACE (FSCM 12345)"),
                ("BLUE PAINT", "pa-pa-025", "(FSCM 67890)"),
            ]
        ),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _list_materials_code_pdf(
            [
                ("RED PAINT", "pa-pa-024", "ACME AEROSPACE"),
                ("BLUE PAINT", "pa-pa-025", "ACME COMPONENTS FSCM 12345"),
                ("GREEN PAINT", "pa-pa-026", "ACME PARTS (FSCM 1234)"),
            ]
        ),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert len(invalid_suggestions) == 3
    assert [item.original for item in invalid_suggestions] == [
        "ACME AEROSPACE",
        "ACME COMPONENTS FSCM 12345",
        "ACME PARTS (FSCM 1234)",
    ]


def test_numerical_index_part_numbers_are_sorted_across_logical_pages() -> None:
    rule = _rule("CUSTOM_NI_PART_NUMBER_ORDER")
    valid, valid_suggestions = execute_pdf_rules(
        _numerical_index_pdf([["CM7-7268", "JZAG030TL", "100", "200"], ["250", "400"]]),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _numerical_index_pdf([["CM7-7268", "100", "300"], ["250", "400"]]),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].page == 2
    assert invalid_suggestions[0].original == "250"
    assert "sous-sequence alphanumerique" in invalid_suggestions[0].message


def test_numerical_index_alphanumeric_part_numbers_use_case_insensitive_order() -> None:
    rule = _rule("CUSTOM_NI_PART_NUMBER_ORDER")
    valid, valid_suggestions = execute_pdf_rules(
        _numerical_index_pdf(
            [["CM7-7268", "JZAG030TL", "JZAG100TL"], ["100", "100A", "250"]]
        ),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _numerical_index_pdf([["CM7-7268", "JZAG030TL"], ["JZAG020TL", "250"]]),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].page == 2
    assert invalid_suggestions[0].original == "JZAG020TL"
    assert "sous-sequence alphanumerique" in invalid_suggestions[0].message


def test_numerical_index_reports_only_the_misplaced_block_across_pages() -> None:
    rule = _rule("CUSTOM_NI_PART_NUMBER_ORDER")
    parsed = _numerical_index_pdf(
        [
            ["CM7-7268", "JZAG030TL", "24595", "24601"],
            [
                "13309", "14602", "14910", "14929", "15472", "17554",
                "18128", "189", "19634", "19922", "20533", "20982",
                "22889", "234", "23984", "25635",
            ],
        ]
    )

    results, suggestions = execute_pdf_rules(parsed, [rule])

    assert results[0].status == "FAIL"
    assert [(item.page, item.original) for item in suggestions] == [
        (1, "24595"),
        (1, "24601"),
    ]


def test_numerical_index_reports_one_misplaced_value_without_cascading() -> None:
    rule = _rule("CUSTOM_NI_PART_NUMBER_ORDER")
    results, suggestions = execute_pdf_rules(
        _numerical_index_pdf([["100", "200", "300", "400", "33362", "46126"]]),
        [rule],
    )

    assert results[0].status == "FAIL"
    assert [(item.page, item.original) for item in suggestions] == [(1, "33362")]


def test_ni_rule_scopes_to_index_pages_and_continues_after_an_unreadable_page() -> None:
    rule = _rule("CUSTOM_NI_PART_NUMBER_ORDER")
    parsed = _numerical_index_pdf(
        [["100", "300", "350"], ["150"], ["200", "250", "275", "400"]],
        leading_pages=1,
    )
    unreadable_index_page = parsed.pages[2]
    unreadable_index_page.spans = [
        span for span in unreadable_index_page.spans if span.text.strip().upper() != "PART NUMBER"
    ]
    unreadable_index_page.text = "\n".join(span.text for span in unreadable_index_page.spans)
    document = SimpleNamespace(
        meta_revision_date="JUL 30/26",
        meta_first_issue_date=None,
        meta_last_issue_date=None,
        meta_cmm_number="21-33-13",
    )

    classify_pages(parsed, document)
    results, suggestions = execute_pdf_rules(parsed, [rule], document=document)

    assert parsed.pages[0].page_type != NUMERICAL_INDEX_PAGE_TYPE
    assert all(
        page.page_type == NUMERICAL_INDEX_PAGE_TYPE
        for page in parsed.pages[1:]
    )
    assert results[0].status == "FAIL"
    assert [(item.page, item.original) for item in suggestions] == [
        (2, "300"),
        (2, "350"),
    ]


def test_ni_order_uses_unselected_pages_as_context_for_a_page_range() -> None:
    rule = _rule("CUSTOM_NI_PART_NUMBER_ORDER")
    full = _numerical_index_pdf(
        [["100", "300", "350"], ["150"], ["200", "250", "275", "400"]],
        leading_pages=1,
    )
    unreadable_index_page = full.pages[2]
    unreadable_index_page.spans = [
        span
        for span in unreadable_index_page.spans
        if span.text.strip().upper() != "PART NUMBER"
    ]
    unreadable_index_page.text = "\n".join(
        span.text for span in unreadable_index_page.spans
    )
    partial = filter_pdf_pages(full, [2])

    results, suggestions = execute_pdf_rules(partial, [rule])

    assert results[0].status == "FAIL"
    assert [(item.page, item.original) for item in suggestions] == [
        (2, "300"),
        (2, "350"),
    ]


def test_shop_verification_accepts_numbered_heading_and_reflowed_text() -> None:
    rule = _rule("CUSTOM_INTRODUCTION_SHOP_VERIFICATION")
    observed = (
        "INTRODUCTION\n1. Shop Verification\nA.\n"
        "Verification of the procedures in this manual\n(1)\n"
        "The shop verification will be done at the first repair of the\n"
        "equipment."
    )

    results, suggestions = execute_pdf_rules(
        _note_page_pdf(observed, INTRODUCTION_PAGE_TYPE),
        [rule],
        document=SimpleNamespace(meta_manufacturer="Airbus"),
    )

    assert results[0].status == "PASS"
    assert suggestions == []


def test_missing_shop_verification_uses_the_central_blank_area_for_its_bbox() -> None:
    rule = _rule("CUSTOM_INTRODUCTION_SHOP_VERIFICATION")
    page = ParsedPage(
        page=1,
        text="INTRODUCTION\n1. General\nExisting introduction text.",
        page_type=INTRODUCTION_PAGE_TYPE,
        spans=[
            Span(
                text="INTRODUCTION",
                bbox=(220.0, 88.0, 360.0, 102.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
            Span(
                text="1. General",
                bbox=(86.0, 116.0, 155.0, 130.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
            Span(
                text="Existing introduction text.",
                bbox=(108.0, 145.0, 300.0, 159.0),
                page=1,
                font="Arial",
                size=10.0,
            ),
            Span(
                text="Page 1\nJUL 27/26",
                bbox=(40.0, 760.0, 300.0, 780.0),
                page=1,
                font="Arial",
                size=8.0,
            ),
        ],
    )

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False),
        [rule],
        document=SimpleNamespace(meta_manufacturer="Airbus"),
    )

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1
    assert suggestions[0].bbox is not None
    assert suggestions[0].bbox[1] > 200.0
    assert suggestions[0].bbox[3] < 700.0


def _note_page_pdf(text: str, page_type: str) -> ParsedPdf:
    page = ParsedPage(page=1, text=text, page_type=page_type)
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


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


def test_tp1_page_type_requires_both_anchor_and_marker_in_the_footer() -> None:
    parsed = ParsedPdf(
        page_count=2,
        pages=[
            _page_with_footer_lines(1, ["Revision: JUL 27/26", "Not a marker"]),
            _page_with_footer_lines(2, ["Unrelated line", "TP1"]),
        ],
        full_text="",
        is_signed=False,
    )

    page_types = identify_tp1_pages(parsed, "JUL 27/26")

    assert page_types == {"1": None, "2": None}


def test_tp1_page_type_is_read_from_the_footer_cmm_number() -> None:
    parsed = ParsedPdf(
        page_count=2,
        pages=[
            _page_with_footer_lines(1, ["CMM: 79-30-02", "TP 1"]),
            _page_with_footer_lines(2, ["CMM: 79-30-02", "Other", "TP1"]),
        ],
        full_text="",
        is_signed=False,
    )

    page_types = identify_tp1_pages(parsed, "JUL 27/26", "79-30-02")

    assert page_types == {"1": "TP1", "2": "TP1"}
    assert parsed.pages[0].page_type == TP1_PAGE_TYPE
    assert parsed.pages[1].page_type == TP1_PAGE_TYPE


def _tp1_address_pdf(text: str, *, page_type: str | None = TP1_PAGE_TYPE) -> ParsedPdf:
    page = ParsedPage(page=1, text=text, page_type=page_type)
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def test_tp1_address_rule_requires_the_exact_thales_address() -> None:
    rule = _rule("CUSTOM_TP1_THALES_ADDRESS")
    valid_text = (
        "(F9111)\n"
        "75-77 Avenue Marcel Dassault\n"
        "33700 Mérignac - France\n"
        "Tel : +33 (0)5 24 44 77 40\n"
        "www.thalesgroup.com"
    )

    valid, valid_suggestions = execute_pdf_rules(_tp1_address_pdf(valid_text), [rule])
    missing_element, missing_element_suggestions = execute_pdf_rules(
        _tp1_address_pdf(valid_text.replace("(F9111)\n", "")),
        [rule],
    )
    not_tp1, not_tp1_suggestions = execute_pdf_rules(
        _tp1_address_pdf(valid_text, page_type=None),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []

    # Adresse presente mais un element precis manquant (ici le code CAGE) :
    # doit rester un FAIL visible, pas juste une entree silencieuse dans les
    # controles compiles — d'ou un commentaire pose sur la page concernee.
    assert missing_element[0].status == "FAIL"
    assert len(missing_element_suggestions) == 1
    assert missing_element_suggestions[0].page == 1
    assert "F9111" in missing_element_suggestions[0].message
    assert missing_element_suggestions[0].message == (
        "Règle non satisfaite : adresse THALES non conforme. "
        "Element attendu : (F9111)"
    )

    assert not_tp1 == []
    assert not_tp1_suggestions == []


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


def test_title_page_copyright_matches_revision_year_in_footer() -> None:
    rule = _rule("CUSTOM_TITLE_PAGE_COPYRIGHT")
    valid_footer = (
        "© 1973-2026 THALES AVS FRANCE SAS. This document and any data included "
        "are the property of THALES AVS FRANCE SAS. They cannot be reproduced, "
        "disclosed or used without the company's prior written approval"
    )
    invalid_year_footer = valid_footer.replace("1973-2026", "1973-2025")
    invalid_start_year_footer = valid_footer.replace("1973-2026", "1974-2026")
    document = SimpleNamespace(
        meta_first_issue_date="JUL 30/73",
        meta_revision_date="JUL 27/26",
    )

    valid, valid_suggestions = execute_pdf_rules(
        _title_page_copyright_pdf(valid_footer), [rule], document=document
    )
    uppercase, uppercase_suggestions = execute_pdf_rules(
        _title_page_copyright_pdf(valid_footer.upper()), [rule], document=document
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _title_page_copyright_pdf(invalid_year_footer), [rule], document=document
    )
    invalid_start, invalid_start_suggestions = execute_pdf_rules(
        _title_page_copyright_pdf(invalid_start_year_footer), [rule], document=document
    )
    missing, missing_suggestions = execute_pdf_rules(
        _title_page_copyright_pdf("Title page footer without copyright"),
        [rule],
        document=document,
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert uppercase[0].status == "PASS"
    assert uppercase_suggestions == []
    assert invalid[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        ("2025", "2026")
    ]
    assert invalid_start[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_start_suggestions] == [
        ("1974", "1973")
    ]
    assert extract_year("JUL 30/73") == "1973"
    assert extract_year("JUL 30/49") == "2049"
    assert extract_year("JUL 30/50") == "1950"
    assert missing[0].status == "FAIL"
    # Copyright entierement absent (pas seulement une annee erronee) : pas de
    # span a remplacer, mais le FAIL doit rester visible via un commentaire.
    assert len(missing_suggestions) == 1
    assert missing_suggestions[0].original == ""
    assert missing_suggestions[0].page == 1


def test_title_page_copyright_checks_every_selected_footer_page() -> None:
    rule = _rule("CUSTOM_TITLE_PAGE_COPYRIGHT")
    valid_footer = (
        "© 1973-2026 THALES AVS FRANCE SAS. This document and any data included "
        "are the property of THALES AVS FRANCE SAS. They cannot be reproduced, "
        "disclosed or used without the company's prior written approval"
    )
    invalid_footer = valid_footer.replace("1973-2026", "1973-2025")

    results, suggestions = execute_pdf_rules(
        _title_page_copyright_pages({1: valid_footer, 3: invalid_footer}),
        [rule],
        document=SimpleNamespace(
            meta_first_issue_date="JUL 30/73",
            meta_revision_date="JUL 27/26",
        ),
    )

    assert results[0].status == "FAIL"
    assert results[0].evidence is not None
    assert results[0].evidence.page == "3"
    assert [
        (item.rule_code, item.page, item.original, item.proposed)
        for item in suggestions
    ] == [("CUSTOM_TITLE_PAGE_COPYRIGHT", 3, "2025", "2026")]


def test_title_page_copyright_reports_mismatches_from_multiple_checks_and_pages() -> None:
    rule = _rule("CUSTOM_TITLE_PAGE_COPYRIGHT")
    valid_footer = (
        "© 1973-2026 THALES AVS FRANCE SAS. This document and any data included "
        "are the property of THALES AVS FRANCE SAS. They cannot be reproduced, "
        "disclosed or used without the company's prior written approval"
    )
    first_invalid_footer = valid_footer.replace("1973-2026", "1973-2025")
    second_invalid_footer = valid_footer.replace("1973-2026", "1970-2026")

    results, suggestions = execute_pdf_rules(
        _title_page_copyright_pages({3: first_invalid_footer, 4: second_invalid_footer}),
        [rule],
        document=SimpleNamespace(
            meta_first_issue_date="JUL 30/73",
            meta_revision_date="JUL 27/26",
        ),
    )

    assert results[0].status == "FAIL"
    assert [
        (item.page, item.original, item.proposed)
        for item in suggestions
    ] == [(3, "2025", "2026"), (4, "1970", "1973")]


def test_copyright_position_matches_pdf_page_parity_and_coordinates() -> None:
    rule = _rule("CUSTOM_COPYRIGHT_POSITION")
    points_per_cm = 72.0 / 2.54
    page_positions = {
        1: (3.03, 26.51),
        2: (1.76, 26.51),
        3: (3.03, 26.51),
        4: (1.76, 26.51),
    }

    def build_pdf(
        overrides: dict[int, tuple[float, float]] | None = None,
        *,
        missing_copyright_page: int | None = None,
        no_text_layer_pages: set[int] | None = None,
    ) -> ParsedPdf:
        overrides = overrides or {}
        no_text_layer_pages = no_text_layer_pages or set()
        pages = []
        for page_number, expected_position in page_positions.items():
            if page_number in no_text_layer_pages:
                pages.append(
                    ParsedPage(
                        page=page_number,
                        text="",
                        spans=[],
                        has_text_layer=False,
                    )
                )
                continue
            text = f"Page {page_number} body."
            spans = [
                Span(
                    text=text,
                    bbox=(40.0, 100.0, 200.0, 112.0),
                    page=page_number,
                    font="Arial",
                    size=10.0,
                )
            ]
            if page_number != missing_copyright_page:
                x_cm, y_cm = overrides.get(page_number, expected_position)
                copyright = "© 1966-2026 THALES AVS FRANCE SAS."
                spans.append(
                    Span(
                        text=copyright,
                        bbox=(
                            x_cm * points_per_cm,
                            y_cm * points_per_cm,
                            x_cm * points_per_cm + 200.0,
                            y_cm * points_per_cm + 8.0,
                        ),
                        page=page_number,
                        font="Arial",
                        size=6.0,
                    )
                )
                text = f"{text}\n{copyright}"
            pages.append(ParsedPage(page=page_number, text=text, spans=spans))
        return ParsedPdf(
            page_count=4,
            pages=pages,
            full_text="\n".join(page.text for page in pages),
            is_signed=False,
        )

    valid, _ = execute_pdf_rules(build_pdf(), [rule])
    assert valid[0].status == "PASS"

    invalid_positions = (
        (1, (1.76, 26.51)),
        (2, (3.03, 26.51)),
        (3, (3.03, 26.71)),
    )
    for page_number, position in invalid_positions:
        invalid, _ = execute_pdf_rules(
            build_pdf({page_number: position}),
            [rule],
        )
        assert invalid[0].status == "FAIL"
        assert invalid[0].evidence is not None
        assert invalid[0].evidence.page == str(page_number)

    missing, _ = execute_pdf_rules(
        build_pdf(missing_copyright_page=4),
        [rule],
    )
    assert missing[0].status == "FAIL"
    assert missing[0].evidence is not None
    assert missing[0].evidence.page == "4"

    blank_pages, _ = execute_pdf_rules(
        build_pdf(no_text_layer_pages={2, 4}),
        [rule],
    )
    assert blank_pages[0].status == "INCONCLUSIVE"
    assert blank_pages[0].inconclusive_pages == ["2", "4"]


def test_page_content_position_matches_pdf_page_parity_and_coordinates() -> None:
    rule = _rule("CUSTOM_PAGE_CONTENT_POSITION")
    points_per_cm = 72.0 / 2.54
    page_positions = {
        1: 3.03,
        2: 1.76,
        3: 3.03,
        4: 1.76,
    }

    def build_pdf(overrides: dict[int, float] | None = None) -> ParsedPdf:
        overrides = overrides or {}
        pages = []
        for page_number, expected_x_cm in page_positions.items():
            x_cm = overrides.get(page_number, expected_x_cm)
            lines = [
                PdfLine(
                    text=f"Body line {line_number} on page {page_number}.",
                    bbox=(
                        x_cm * points_per_cm,
                        100.0 + line_number * 12.0,
                        400.0,
                        110.0 + line_number * 12.0,
                    ),
                    block_index=0,
                    line_index=line_number,
                )
                for line_number in range(5)
            ]
            lines.append(
                PdfLine(
                    text="Indented paragraph line.",
                    bbox=(300.0, 180.0, 450.0, 190.0),
                    block_index=1,
                    line_index=0,
                )
            )
            pages.append(
                ParsedPage(
                    page=page_number,
                    text="\n".join(line.text for line in lines),
                    lines=lines,
                )
            )
        return ParsedPdf(
            page_count=4,
            pages=pages,
            full_text="\n".join(page.text for page in pages),
            is_signed=False,
        )

    valid, _ = execute_pdf_rules(build_pdf(), [rule])
    assert valid[0].status == "PASS"

    invalid, _ = execute_pdf_rules(build_pdf({3: 1.76}), [rule])
    assert invalid[0].status == "FAIL"
    assert invalid[0].evidence is not None
    assert invalid[0].evidence.page == "3"


def test_mat_reference_format_is_passed_and_failed_by_the_compiled_executor() -> None:
    rule = _rule("MAT_REF_FORMAT")
    valid, _ = execute_pdf_rules(_pdf("See MAT-24-21-00-001."), [rule])
    invalid, _ = execute_pdf_rules(_pdf("See MAT-24-21-00."), [rule])
    assert valid[0].status == "PASS"
    assert invalid[0].status == "FAIL"


def test_conditional_periodicity_and_dual_torque_are_executed() -> None:
    periodicity = _rule("ATA_FIELD_PERIODICITE")
    missing, _ = execute_pdf_rules(_pdf("Preventive maintenance task."), [periodicity])
    present, _ = execute_pdf_rules(_pdf("Preventive maintenance task. Frequency: 200 FH."), [periodicity])
    assert missing[0].status == "FAIL"
    assert present[0].status == "PASS"

    torque = _rule("ATA_TORQUE_DUAL_UNIT")
    dual, _ = execute_pdf_rules(_pdf("Torque 12 N.m and 9 lb.ft."), [torque])
    single, _ = execute_pdf_rules(_pdf("Torque 12 N.m."), [torque])
    assert dual[0].status == "PASS"
    assert single[0].status == "FAIL"


def test_compiled_rules_produce_pdf_and_docx_evidence() -> None:
    rule = _rule("STE_NO_MAYBE")
    pdf_results, pdf_suggestions = execute_pdf_rules(_pdf("Maybe remove the panel."), [rule])
    docx_results, docx_suggestions = execute_docx_rules(
        [
            Block(
                target_id="dp1",
                index=1,
                zone="body",
                kind="paragraph",
                text="Maybe remove the panel.",
            )
        ],
        [rule],
    )
    assert pdf_results[0].status == "FAIL"
    assert pdf_results[0].evidence is not None
    assert pdf_suggestions[0].rule_code == "STE_NO_MAYBE"
    assert docx_results[0].status == "FAIL"
    assert docx_results[0].evidence is not None
    assert docx_suggestions[0].rule_code == "STE_NO_MAYBE"
