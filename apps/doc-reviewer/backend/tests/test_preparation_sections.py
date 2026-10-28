from __future__ import annotations

import fitz
import pytest

from app.checks.thales_rules.section_detection import (
    classify_preparation_sections,
    page_types_for_titles,
)
from app.parsers.pdf_parser import parse_pdf

PageSpec = tuple[list[str], list[str]]


def _classify(
    pages: list[PageSpec],
    metadata: dict | None = None,
    *,
    table: set[int] | None = None,
    page_titles: dict[str, str] | None = None,
):
    pdf = fitz.open()
    for index, (body, footer) in enumerate(pages, start=1):
        page = pdf.new_page(width=400, height=600)
        for line_number, text in enumerate(body):
            page.insert_text((40, 60 + line_number * 20), text, fontsize=10)
        for line_number, text in enumerate(footer):
            page.insert_text((40, 540 + line_number * 14), text, fontsize=9)
        if table and index in table:
            for y in (200, 230, 260, 290):
                page.draw_line((40, y), (360, y))
    parsed = parse_pdf(pdf.tobytes())
    pdf.close()
    analysis = classify_preparation_sections(parsed, metadata or {}, page_titles)
    return parsed, analysis


def _single(body: list[str], footer: list[str], **kwargs):
    parsed, analysis = _classify([(body, footer)], **kwargs)
    return parsed.pages[0].page_type, analysis[1]


HIGHLIGHTS_BODY = [
    "REVISION No. 03 DATED JUL 27/26",
    "Chapter/Section and Page No",
    "Designation",
    "Description of Change",
]


@pytest.mark.parametrize(
    ("footer", "expected"),
    [
        ("Highlights Page 1", "HIGHLIGHTS_PAGE_1"),
        ("Highlights Page 2", "HIGHLIGHTS"),
        ("Higlight Page 3", "HIGHLIGHTS"),
    ],
)
def test_highlights_footer_and_table_confirm_the_page(footer: str, expected: str) -> None:
    page_type, info = _single(HIGHLIGHTS_BODY, [footer])

    assert page_type == expected
    assert info["classification_status"] == "confirmed"
    assert {signal["family"] for signal in info["classification_signals"]} == {"footer", "content"}


@pytest.mark.parametrize(
    ("body", "footer", "expected"),
    [
        (["RECORD OF REVISIONS", "REV. No.", "REVISION DATE", "INSERTION DATE", "BY"], "ROR Page 1", "ROR"),
        (["RECORD OF REVISIONS", "REV. No.", "REVISION DATE", "INSERTION DATE", "BY"], "RR-2", "ROR"),
        (["LIST OF EFFECTIVE PAGES", "SUBJECT PAGE DATE SUBJECT PAGE DATE"], "LEP Page 1", "LEP"),
        (["LIST OF EFFECTIVE PAGES", "SUBJECT PAGE DATE"], "LEP-1", "LEP"),
        (["INTRODUCTION", "Some text"], "INTRO Page 1", "INTRODUCTION"),
        (["INTRODUCTION"], "INTRO-1", "INTRODUCTION"),
        (["TABLE OF CONTENTS"], "TC Page 1", "TABLE_OF_CONTENTS"),
        (["TABLE OF CONTENTS"], "TC-2", "TABLE_OF_CONTENTS"),
        (["VENDOR CODE LIST"], "Page 1001", "VENDOR_CODE_LIST"),
    ],
)
def test_title_and_footer_alias_confirm_each_section(body, footer, expected) -> None:
    page_type, info = _single(body, [footer])

    assert page_type == expected
    assert info["classification_status"] == "confirmed"


@pytest.mark.parametrize(
    ("footer", "title", "expected"),
    [
        ("Page 101", "TESTING AND FAULT ISOLATION", "TESTING"),
        ("Page 199", "TESTING AND FAULT ISOLATION", "TESTING"),
        ("Page 601", "REPAIR", "REPAIR"),
        ("Page 699", "REPAIR", "REPAIR"),
        ("Page 701", "ASSEMBLY", "ASSEMBLY"),
        ("Page 799", "ASSEMBLY AND STORAGE", "ASSEMBLY"),
        ("Page 750", "ASSEMBLY INCLUDING STORAGE", "ASSEMBLY"),
        ("Page 750", "ASSEMBLY (INCLUDING STORAGE)", "ASSEMBLY"),
        ("Page 1999", "VENDOR CODE LIST", "VENDOR_CODE_LIST"),
    ],
)
def test_numeric_footer_ranges_are_inclusive_and_agree_with_title(footer, title, expected) -> None:
    page_type, info = _single([title], [footer])

    assert page_type == expected
    assert info["classification_status"] == "confirmed"


@pytest.mark.parametrize("footer", ["Page 100", "Page 200", "Page 600", "Page 700", "Page 800", "Page 1000"])
def test_numbers_outside_documented_ranges_leave_page_unclassified(footer: str) -> None:
    page_type, info = _single(["Plain body text"], [footer])

    assert page_type is None
    assert info["classification_status"] == "unclassified"


def test_single_signal_is_partial_and_no_signal_is_unclassified() -> None:
    title_only, title_info = _single(["REPAIR"], ["JUL 27/26"])
    footer_only, footer_info = _single(["Body"], ["Page 650"])
    tp1_footer, tp1_footer_info = _single(["Title page text"], ["TP 1"])
    none, none_info = _single(["Body"], [])

    assert (title_only, title_info["classification_status"]) == ("REPAIR", "partial")
    assert (footer_only, footer_info["classification_status"]) == ("REPAIR", "partial")
    assert (tp1_footer, tp1_footer_info["classification_status"]) == ("TP1", "partial")
    assert (none, none_info["classification_status"]) == (None, "unclassified")


def test_unknown_standalone_title_is_not_classified() -> None:
    page_type, info = _single(["HYDRAULIC PUMP OVERHAUL"], [])

    assert page_type is None
    assert info["classification_status"] == "unclassified"
    assert info["classification_signals"] == []
    assert info["classification_notes"] == []


def test_unknown_ocr_title_is_not_classified() -> None:
    from app.parsers.pdf_parser import ParsedPage, ParsedPdf

    parsed = ParsedPdf(
        page_count=1,
        pages=[
            ParsedPage(
                page=1,
                text="HYDRAULIC PUMP OVERHAUL\nInstructions for servicing",
                has_text_layer=False,
            )
        ],
        full_text="HYDRAULIC PUMP OVERHAUL\nInstructions for servicing",
        is_signed=False,
    )

    analysis = classify_preparation_sections(parsed, {})

    assert parsed.pages[0].page_type is None
    assert analysis[1]["classification_status"] == "unclassified"
    assert analysis[1]["classification_signals"] == []
    assert analysis[1]["classification_notes"] == []


def test_configured_titles_start_sections_and_continuations_inherit_them() -> None:
    page_titles = page_types_for_titles(["CUSTOM INTRODUCTION", "CLEANING"])
    parsed, analysis = _classify(
        [
            (["CUSTOM INTRODUCTION"], []),
            (["Procedures continue on this page."], []),
            (["CLEANING"], []),
            (["The cleaning process continues."], []),
            (["HYDRAULIC PUMP OVERHAUL"], []),
            (["Procedures continue on this page."], []),
        ],
        page_titles=page_titles,
    )

    assert [page.page_type for page in parsed.pages] == [
        "CUSTOM INTRODUCTION",
        "CUSTOM INTRODUCTION",
        "CLEANING",
        "CLEANING",
        "CLEANING",
        "CLEANING",
    ]
    assert analysis[1]["classification_status"] == "partial"
    assert analysis[2]["classification_signals"][0]["detail"] == (
        "continuation: CUSTOM INTRODUCTION page 2"
    )
    assert analysis[4]["classification_signals"][0]["detail"] == (
        "continuation: CLEANING page 2"
    )
    assert analysis[5]["classification_signals"][0]["detail"] == (
        "continuation: CLEANING page 3"
    )
    assert analysis[5]["classification_notes"] == []
    assert analysis[6]["classification_signals"][0]["detail"] == (
        "continuation: CLEANING page 4"
    )


def test_unknown_sentence_from_page_body_is_not_used_as_a_title() -> None:
    page_type, info = _single(["This is a body sentence."], [])

    assert page_type is None
    assert info["classification_status"] == "unclassified"


def test_conflicting_signals_stay_unclassified_and_list_candidates() -> None:
    page_type, info = _single(["TESTING AND FAULT ISOLATION"], ["Page 650"])

    assert page_type is None
    assert info["classification_status"] == "conflict"
    assert info["classification_candidates"] == ["REPAIR", "TESTING"]


def test_lep_and_toc_pages_do_not_inherit_titles_they_list() -> None:
    lep_type, _ = _single(
        ["LIST OF EFFECTIVE PAGES", "SUBJECT PAGE DATE", "INTRODUCTION", "REPAIR"], ["LEP Page 1"]
    )
    toc_type, _ = _single(["TABLE OF CONTENTS", "INTRODUCTION", "REPAIR"], ["TC Page 1"])

    assert lep_type == "LEP"
    assert toc_type == "TABLE_OF_CONTENTS"


def test_special_tools_sub_sections_and_table_with_footer_aliases() -> None:
    for footer in ("Page 901", "LM Page 2", "LM-3"):
        page_type, info = _single(["List of consumables (cont'd)"], [footer], table={1})
        assert page_type == "SPECIAL_TOOLS"
        assert info["classification_status"] == "confirmed"
    for title in ("Consumables", "List of materials", "Materials"):
        page_type, _ = _single([title], ["Page 950"])
        assert page_type == "SPECIAL_TOOLS"


def test_generic_special_tools_heading_does_not_override_another_footer() -> None:
    page_type, info = _single(["Materials"], ["Page 650"])

    assert page_type == "REPAIR"
    assert info["classification_status"] == "partial"


def test_tp1_follows_the_first_odd_page_after_highlights() -> None:
    pages = [
        (HIGHLIGHTS_BODY, ["Highlights Page 1"]),
        (HIGHLIGHTS_BODY, ["Highlights Page 2"]),
        (HIGHLIGHTS_BODY, ["Highlights Page 3"]),
        ([], []),
        (["Title page text"], []),
    ]

    parsed, analysis = _classify(pages)

    assert [page.page_type for page in parsed.pages] == [
        "HIGHLIGHTS_PAGE_1",
        "HIGHLIGHTS",
        "HIGHLIGHTS",
        None,
        "TP1",
    ]
    assert analysis[5]["classification_status"] == "partial"
    assert analysis[5]["classification_signals"][0]["family"] == "position"


def test_tp1_sequence_position_is_not_forced_on_pages_with_other_evidence() -> None:
    pages = [
        (HIGHLIGHTS_BODY, ["Highlights Page 1"]),
        (HIGHLIGHTS_BODY, ["Highlights Page 2"]),
        (["INTRODUCTION"], ["Page 150"]),
    ]

    parsed, _ = _classify(pages)

    assert parsed.pages[2].page_type is None


def test_tp1_footer_off_sequence_is_flagged() -> None:
    pages = [
        (HIGHLIGHTS_BODY, ["Highlights Page 1"]),
        (HIGHLIGHTS_BODY, ["Highlights Page 2"]),
        (HIGHLIGHTS_BODY, ["Highlights Page 3"]),
        (["Title page"], ["TP-1"]),
    ]

    parsed, analysis = _classify(pages)

    assert parsed.pages[3].page_type == "TP1"
    assert analysis[4]["classification_status"] == "partial"
    assert "page 5" in analysis[4]["classification_notes"][0]


def test_tp1_content_comes_from_the_mapping_not_from_invented_fields() -> None:
    metadata = {"meta_cmm_number": "79-30-02", "meta_first_issue_date": "JUL 1966"}
    body = ["OVERHAUL MANUAL", "CMM 79-30-02", "First issue: JUL 1966"]

    page_type, info = _single(body, ["TP Page 1"], metadata=metadata)
    no_mapping, no_mapping_info = _single(body, ["TP Page 1"])

    assert (page_type, info["classification_status"]) == ("TP1", "confirmed")
    assert (no_mapping, no_mapping_info["classification_status"]) == ("TP1", "partial")


def test_existing_classifier_types_are_kept_when_no_section_signal_exists() -> None:
    pdf = fitz.open()
    pdf.new_page(width=400, height=600).insert_text((40, 60), "Body", fontsize=10)
    parsed = parse_pdf(pdf.tobytes())
    pdf.close()
    parsed.pages[0].page_type = "TP2"

    analysis = classify_preparation_sections(parsed, {})

    assert parsed.pages[0].page_type == "TP2"
    assert analysis[1]["classification_status"] == "detected"


def test_legacy_type_contradicting_new_signals_is_a_conflict() -> None:
    pdf = fitz.open()
    page = pdf.new_page(width=400, height=600)
    page.insert_text((40, 60), "REPAIR", fontsize=10)
    page.insert_text((40, 540), "Page 650", fontsize=9)
    parsed = parse_pdf(pdf.tobytes())
    pdf.close()
    parsed.pages[0].page_type = "STORAGE"

    analysis = classify_preparation_sections(parsed, {})

    assert parsed.pages[0].page_type is None
    assert analysis[1]["classification_status"] == "conflict"
