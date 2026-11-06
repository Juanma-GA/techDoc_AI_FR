"""Compiled catalog: PNR headers, document types and Highlights legend rules."""

from __future__ import annotations

from types import SimpleNamespace

from app.checks.thales_rules.ata100.page_classifier import (
    HIGHLIGHTS_PAGE_TYPE,
    HIGHLIGHTS_FIRST_PAGE_TYPE,
    TP1_PAGE_TYPE,
)
from app.checks.thales_rules.ata100.rules import DOCUMENT_TYPES
from app.parsers.pdf_parser import (
    ParsedPage,
    ParsedPdf,
    PdfLine,
    Span,
)
from tests.helpers.compiled_catalog import (
    _rule,
    execute_pdf_rules,
)


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

    abbreviated_mapping = SimpleNamespace(
        meta_pnr_number=["65806-002-1", "S231T120-1"]
    )
    abbreviated, abbreviated_suggestions = execute_pdf_rules(
        build_page("65806-002"), [rule], document=abbreviated_mapping
    )
    partial_segment, _partial_segment_suggestions = execute_pdf_rules(
        build_page("65806-00"), [rule], document=abbreviated_mapping
    )

    assert abbreviated[0].status == "PASS"
    assert abbreviated_suggestions == []
    assert partial_segment[0].status == "FAIL"


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


def test_highlights_pnr_header_accepts_wildcard_shortcuts_covering_mapping_values() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    mapping = [
        "C4171ADM7",
        "C4171AHAM1",
        "C4171AEM7",
        "C4171AJAM1",
        "C4171AFM5",
        "C4171AKAM1",
        "C4171AGM5",
        "C4171ALAM1",
        "C4355AAM",
    ]

    page = _document_type_header_page(
        "PNR : C4171Axxx/C4355AAMx",
        page_type=HIGHLIGHTS_PAGE_TYPE,
    )
    parsed = ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False)
    results, suggestions = execute_pdf_rules(
        parsed,
        [rule],
        document=SimpleNamespace(meta_pnr_number=mapping),
    )

    assert results[0].status == "PASS"
    assert suggestions == []


def test_highlights_pnr_header_rejects_wildcard_shortcuts_missing_mapping_families() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    mapping = ["C4171ADM7", "C4171AHAM1", "C4355AAM"]
    page = _document_type_header_page(
        "PNR : C4171Axxx",
        page_type=HIGHLIGHTS_PAGE_TYPE,
    )
    parsed = ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False)

    results, suggestions = execute_pdf_rules(
        parsed,
        [rule],
        document=SimpleNamespace(meta_pnr_number=mapping),
    )

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1


def test_highlights_pnr_header_does_not_treat_a_mapped_x_as_a_wildcard() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    mapping = ["C4171ADM7", "C4171Axxx"]
    page = _document_type_header_page(
        "PNR : C4171Axxx",
        page_type=HIGHLIGHTS_PAGE_TYPE,
    )
    parsed = ParsedPdf(page_count=1, pages=[page], full_text=page.text, is_signed=False)

    results, suggestions = execute_pdf_rules(
        parsed,
        [rule],
        document=SimpleNamespace(meta_pnr_number=mapping),
    )

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1


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
