"""Compiled catalog: page type classification and shop verification rules."""

from __future__ import annotations

from types import SimpleNamespace

from app.checks.thales_rules.ata100.operations import shop_verification_text
from app.checks.thales_rules.ata100.page_classifier import (
    HIGHLIGHTS_FIRST_PAGE_TYPE,
    INTRODUCTION_PAGE_TYPE,
    TP2_PAGE_TYPE,
    REPAIR_PAGE_TYPE,
    STORAGE_PAGE_TYPE,
    TESTING_PAGE_TYPE,
    TP1_PAGE_TYPE,
    classify_pages,
    identify_note_pages,
    identify_introduction_pages,
    identify_tp1_pages,
)
from app.checks.thales_rules.ata100.rules import IMPORTANT_NOTICE_TEXT as _IMPORTANT_NOTICE_TEXT
from app.parsers.pdf_parser import (
    ParsedPage,
    ParsedPdf,
    Span,
)
from tests.helpers.compiled_catalog import (
    _note_page_pdf,
    _page_with_footer_lines,
    _rule,
    _tp2_notice_pdf,
    execute_pdf_rules,
)


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
