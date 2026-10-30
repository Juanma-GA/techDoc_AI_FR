"""Compiled catalog: footers (CMM, revision, first issue), TP1/TP2, logo, copyright and position rules."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.checks.thales_rules.ata100.page_classifier import (
    TP2_PAGE_TYPE,
    TP1_PAGE_TYPE,
)
from app.checks.thales_rules.ata100.rules import IMPORTANT_NOTICE_TEXT as _IMPORTANT_NOTICE_TEXT
from app.core.compiled_rule_operators import extract_year
from app.core.page_range import filter_pdf_pages
from app.parsers.pdf_parser import (
    ParsedPage,
    ParsedPdf,
    PdfLine,
    Span,
)
from tests.helpers.compiled_catalog import (
    _numbered_chapter_pdf,
    _rule,
    _tp2_notice_pdf,
    execute_pdf_rules,
)


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
