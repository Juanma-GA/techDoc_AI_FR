"""Compiled catalog: Highlights pages (mapping values, ATA number, descriptions)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.checks.thales_rules.ata100.page_classifier import (
    HIGHLIGHTS_PAGE_TYPE,
    HIGHLIGHTS_FIRST_PAGE_TYPE,
    TP1_PAGE_TYPE,
    classify_pages,
    identify_note_pages,
)
from app.parsers.pdf_parser import (
    ParsedPage,
    ParsedPdf,
    Span,
)
from tests.helpers.compiled_catalog import (
    _page_with_footer_lines,
    _rule,
    execute_pdf_rules,
)


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
        _highlights_structure_pdf([("Repair", "R", "")]),
        [rule],
    )
    ordinary_present, present_suggestions = execute_pdf_rules(
        _highlights_structure_pdf([("Repair", "R", "Corrected assembly instruction")]),
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


@pytest.mark.parametrize("page_label", ["Page 601", "Pages 1007 to 1010"])
def test_revised_highlights_page_only_rows_do_not_require_a_description(
    page_label: str,
) -> None:
    results, suggestions = execute_pdf_rules(
        _highlights_structure_pdf([(page_label, "R", "")]),
        [_rule("CUSTOM_HIGHLIGHTS_REVISED_DESCRIPTION")],
    )

    assert results[0].status == "PASS"
    assert suggestions == []


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
