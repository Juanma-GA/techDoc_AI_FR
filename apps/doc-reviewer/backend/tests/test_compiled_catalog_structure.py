"""Compiled catalog: chapter sequence, bookmarks, list of materials and numerical index rules."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.checks.thales_rules.ata100.page_classifier import (
    NUMERICAL_INDEX_PAGE_TYPE,
    classify_pages,
    identify_numerical_index_pages,
)
from app.core.page_range import filter_pdf_pages
from app.parsers.pdf_parser import (
    ParsedPage,
    ParsedPdf,
    PdfBookmark,
    PdfLine,
    Span,
)
from tests.helpers.compiled_catalog import (
    _numbered_chapter_pdf,
    _rule,
    execute_pdf_rules,
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
    ("bookmark_title", "page_title", "expected_status", "expected_proposed"),
    [
        (
            "LIST OF EFFECTIVE PAGES",
            "LIST OF EFFECTIVES PAGES",
            "FAIL",
            "LIST OF EFFECTIVE PAGES",
        ),
        (
            "LIST EFFECTIVE PAGES",
            "LIST OF EFFECTIVES PAGES",
            "FAIL",
            "LIST EFFECTIVE PAGES",
        ),
        (
            "LIST OF EFFECTIVE PAGES",
            "LIST OF EFECTIVE PAGES",
            "FAIL",
            "LIST OF EFFECTIVE PAGES",
        ),
        ("Illustrated Parts List", "ILLUSTRATED PART LIS", "FAIL", "Illustrated Parts List"),
        ("REPAIR PROCEDURE", "REPAIR PROCEDURES", "FAIL", "REPAIR PROCEDURE"),
        ("REPAIR PROCEDURE", "INTRODUCTION", "FAIL", ""),
        ("REPAIR PROCEDURE 101", "REPAIR PROCEDURE 102", "FAIL", ""),
        ("CHECK", "CHEEK", "FAIL", ""),
    ],
)
def test_pdf_bookmark_tolerates_small_title_typos_but_not_wrong_destinations(
    bookmark_title: str,
    page_title: str,
    expected_status: str,
    expected_proposed: str,
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
    if expected_proposed:
        assert suggestions[0].original == page_title
        assert suggestions[0].proposed == expected_proposed
        assert "faute d'orthographe" in suggestions[0].message
    elif suggestions:
        assert suggestions[0].proposed == ""


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
    assert [(item.original, item.page) for item in suggestions] == [
        (header, 1),
        ("LIST OF EFFECTIVE PAGES", 1),
    ]
    assert suggestions[1].proposed == "LIST OF EFFECTIVE PAGE"
    assert "faute d'orthographe" in suggestions[1].message


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
                ("RED PAINT", "pa-pa-024", "ACME AEROSPACE (FSCM 12345) France"),
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


def test_list_of_materials_supplier_country_must_be_uppercase() -> None:
    rule = _rule("CUSTOM_LIST_OF_MATERIALS_SUPPLIER_COUNTRY_UPPERCASE")
    valid, valid_suggestions = execute_pdf_rules(
        _list_materials_code_pdf(
            [
                ("RED PAINT", "pa-pa-024", "ACME AEROSPACE (FSCM 12345) FRANCE"),
                ("BLUE PAINT", "pa-pa-025", "ACME COMPONENTS (FSCM 67890) UNITED KINGDOM"),
                ("GREEN PAINT", "pa-pa-026", "ACME PARTS (FSCM 12345)"),
            ]
        ),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _list_materials_code_pdf(
            [
                ("RED PAINT", "pa-pa-024", "ACME AEROSPACE (FSCM 12345) France"),
                ("BLUE PAINT", "pa-pa-025", "ACME COMPONENTS (FSCM 67890) Côte d'Ivoire"),
            ]
        ),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        (
            "ACME AEROSPACE (FSCM 12345) France",
            "ACME AEROSPACE (FSCM 12345) FRANCE",
        ),
        (
            "ACME COMPONENTS (FSCM 67890) Côte d'Ivoire",
            "ACME COMPONENTS (FSCM 67890) CÔTE D'IVOIRE",
        ),
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
