"""Coverage for the built-in standards expressed as CompiledRule."""

from __future__ import annotations

from types import SimpleNamespace

from app.checks.standards import BUILTIN_STANDARDS, serialize_builtin_version
from app.checks.standards.thales_custom import (
    HIGHLIGHTS_PAGE_TYPE,
    HIGHLIGHTS_FIRST_PAGE_TYPE,
    TP2_PAGE_TYPE,
    REPAIR_PAGE_TYPE,
    STORAGE_PAGE_TYPE,
    TESTING_PAGE_TYPE,
    TP1_PAGE_TYPE,
    _IMPORTANT_NOTICE_TEXT,
    classify_pages,
    identify_note_pages,
    identify_tp1_pages,
)

from app.core.compiled_rule_executor import execute_docx_rules, execute_pdf_rules
from app.core.compiled_rules import CompiledRule
from app.core.standard_rule_compiler import compile_standard_rule
from app.parsers.docx_parser import Block
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, Span


def _rule(code: str) -> CompiledRule:
    for spec in BUILTIN_STANDARDS:
        for label in spec["versions"]:
            for rule in spec["versions"][label]:
                if rule.id == code:
                    return rule
    raise AssertionError(f"Unknown built-in rule: {code}")


def _pdf(text: str) -> ParsedPdf:
    page = ParsedPage(page=1, text=text, spans=[])
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


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
                assert metadata[compiled.id]["message"]
    assert total == 60


def test_user_cmm_rule_uses_the_document_context_value() -> None:
    rule = _rule("CUSTOM_CMM_NUMBER")

    valid, _ = execute_pdf_rules(
        _cmm_footer_pdf("79-30-02"),
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
    missing, missing_suggestions = execute_pdf_rules(
        _tp2_notice_pdf("TP2 notice missing", page_type=TP2_PAGE_TYPE),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].proposed == "property"
    assert "Texte attendu" in invalid_suggestions[0].message
    assert "sole propriety" in invalid_suggestions[0].original
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


def _revision_date_footer_pdf(footer: str) -> ParsedPdf:
    body = "Title page body."
    text = f"{body}\n{footer}"
    page = ParsedPage(
        page=1,
        text=text,
        spans=[
            Span(text=body, bbox=(40.0, 100.0, 200.0, 120.0), page=1, font="Arial", size=10.0),
            Span(text=footer, bbox=(40.0, 760.0, 300.0, 780.0), page=1, font="Arial", size=8.0),
        ],
    )
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def test_revision_date_footer_matches_document_context_value() -> None:
    rule = _rule("CUSTOM_REVISION_DATE")
    document = SimpleNamespace(meta_revision_date="JUL 27/26")

    valid, valid_suggestions = execute_pdf_rules(
        _revision_date_footer_pdf("Revision: JUL 27/26"),
        [rule],
        document=document,
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _revision_date_footer_pdf("Revision: JUL 27/25"),
        [rule],
        document=document,
    )
    missing, missing_suggestions = execute_pdf_rules(
        _revision_date_footer_pdf("Footer without a revision date"),
        [rule],
        document=document,
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        ("5", "6")
    ]
    assert missing[0].status == "FAIL"
    # Date entierement absente (pas seulement erronee) : pas de span a
    # remplacer, mais le FAIL doit rester visible via un commentaire.
    assert len(missing_suggestions) == 1
    assert missing_suggestions[0].original == ""
    assert missing_suggestions[0].page == 1


def test_footer_required_values_are_checked_on_each_page() -> None:
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
    revision_results, revision_suggestions = execute_pdf_rules(
        parsed,
        [_rule("CUSTOM_REVISION_DATE")],
        document=document,
    )

    assert cmm_results[0].status == "FAIL"
    assert [(item.page, item.original, item.proposed) for item in cmm_suggestions] == [
        (2, "1", "2")
    ]
    assert revision_results[0].status == "FAIL"
    assert [
        (item.page, item.original, item.proposed) for item in revision_suggestions
    ] == [(2, "JAN", "JUL")]


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


def test_pnr_header_reports_each_invalid_page() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    document = SimpleNamespace(meta_pnr_number="1-879-SB")

    pages = [
        ParsedPage(
            page=page_number,
            page_type=None,
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
        for page_number, pnr in ((1, "1-878-SB"), (2, "1-877-SB"))
    ]

    results, suggestions = execute_pdf_rules(
        ParsedPdf(page_count=2, pages=pages, full_text="\n".join(page.text for page in pages), is_signed=False),
        [rule],
        document=document,
    )

    assert results[0].status == "FAIL"
    assert [(suggestion.page, suggestion.original) for suggestion in suggestions] == [
        (1, "1-878-SB"),
        (2, "1-877-SB"),
    ]


def test_pnr_header_reports_each_invalid_occurrence() -> None:
    rule = _rule("CUSTOM_HIGHLIGHTS_PNR_HEADER")
    document = SimpleNamespace(meta_pnr_number="1-879-SB")
    page = ParsedPage(
        page=1,
        page_type=None,
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


def test_pnr_header_is_not_checked_on_tp1_pages() -> None:
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
    non_tp1_page = ParsedPage(
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
    non_tp1_results, non_tp1_suggestions = execute_pdf_rules(
        ParsedPdf(1, [non_tp1_page], non_tp1_page.text, False),
        [rule],
        document=document,
    )

    assert tp1_results == []
    assert tp1_suggestions == []
    assert non_tp1_results[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in non_tp1_suggestions] == [
        ("1-878-SB", "1-879-SB")
    ]


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
        text="PNR: 1-878-SB\nDocument body - 1-878-SB",
        spans=[
            Span(
                text="PNR: 1-878-SB",
                bbox=(40.0, 100.0, 300.0, 110.0),
                page=2,
                font="Arial",
                size=8.0,
            ),
            Span(
                text="Document body - 1-878-SB",
                bbox=(40.0, 400.0, 300.0, 410.0),
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
        page_count=4,
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
        page_count=2,
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
        ],
        full_text="",
        is_signed=False,
    )

    page_types = identify_note_pages(parsed)

    assert page_types == {"1": None, "2": HIGHLIGHTS_PAGE_TYPE}


def _note_page_pdf(text: str, page_type: str) -> ParsedPdf:
    page = ParsedPage(page=1, text=text, page_type=page_type)
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
            f"TESTING\n{testing_note_intro}\nPressure: 1 bar\n{repair_rh}\n"
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


def test_forbidden_consumables_are_reported_by_one_rule() -> None:
    rule = _rule("CUSTOM_FORBIDDEN_CONSUMABLES")

    valid, valid_suggestions = execute_pdf_rules(
        _pdf("Use approved packaging."),
        [rule],
    )
    invalid, invalid_suggestions = execute_pdf_rules(
        _pdf("Use Silica gel and dessicant bag."),
        [rule],
    )

    assert valid[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid[0].status == "FAIL"
    assert {item.original for item in invalid_suggestions} == {
        "Silica gel",
        "dessicant bag",
    }
    assert {item.proposed for item in invalid_suggestions} == {""}
    assert {item.rule_code for item in invalid_suggestions} == {
        "CUSTOM_FORBIDDEN_CONSUMABLES"
    }


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
        "© 1966-2026 THALES AVS FRANCE SAS. This document and any data included "
        "are the property of THALES AVS FRANCE SAS. They cannot be reproduced, "
        "disclosed or used without the company's prior written approval"
    )
    invalid_year_footer = valid_footer.replace("1966-2026", "1966-2025")
    invalid_start_year_footer = valid_footer.replace("1966-2026", "1967-2026")
    document = SimpleNamespace(meta_revision_date="JUL 27/26")

    valid, valid_suggestions = execute_pdf_rules(
        _title_page_copyright_pdf(valid_footer), [rule], document=document
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
    assert invalid[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_suggestions] == [
        ("2025", "2026")
    ]
    assert invalid_start[0].status == "FAIL"
    assert [(item.original, item.proposed) for item in invalid_start_suggestions] == [
        ("1967", "1966")
    ]
    assert missing[0].status == "FAIL"
    # Copyright entierement absent (pas seulement une annee erronee) : pas de
    # span a remplacer, mais le FAIL doit rester visible via un commentaire.
    assert len(missing_suggestions) == 1
    assert missing_suggestions[0].original == ""
    assert missing_suggestions[0].page == 1


def test_title_page_copyright_checks_every_selected_footer_page() -> None:
    rule = _rule("CUSTOM_TITLE_PAGE_COPYRIGHT")
    valid_footer = (
        "© 1966-2026 THALES AVS FRANCE SAS. This document and any data included "
        "are the property of THALES AVS FRANCE SAS. They cannot be reproduced, "
        "disclosed or used without the company's prior written approval"
    )
    invalid_footer = valid_footer.replace("1966-2026", "1966-2025")

    results, suggestions = execute_pdf_rules(
        _title_page_copyright_pages({1: valid_footer, 3: invalid_footer}),
        [rule],
        document=SimpleNamespace(meta_revision_date="JUL 27/26"),
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
        "© 1966-2026 THALES AVS FRANCE SAS. This document and any data included "
        "are the property of THALES AVS FRANCE SAS. They cannot be reproduced, "
        "disclosed or used without the company's prior written approval"
    )
    first_invalid_footer = valid_footer.replace("1966-2026", "1966-2025")
    second_invalid_footer = valid_footer.replace("1966-2026", "1970-2026")

    results, suggestions = execute_pdf_rules(
        _title_page_copyright_pages({3: first_invalid_footer, 4: second_invalid_footer}),
        [rule],
        document=SimpleNamespace(meta_revision_date="JUL 27/26"),
    )

    assert results[0].status == "FAIL"
    assert [
        (item.page, item.original, item.proposed)
        for item in suggestions
    ] == [(3, "2025", "2026"), (4, "1970", "1966")]


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
