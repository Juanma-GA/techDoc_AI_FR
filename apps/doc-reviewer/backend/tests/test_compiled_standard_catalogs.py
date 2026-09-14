"""Coverage for the built-in standards expressed as CompiledRule."""

from __future__ import annotations

from types import SimpleNamespace

from app.checks.standards import BUILTIN_STANDARDS, serialize_builtin_version
from app.checks.standards.thales_custom import (
    HIGHLIGHTS_PAGE_TYPE,
    TP1_PAGE_TYPE,
    classify_pages,
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


def _cmm_footer_pdf(footer: str) -> ParsedPdf:
    body = "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00."
    text = f"{body}\n{footer}"
    page = ParsedPage(
        page=1,
        text=text,
        spans=[
            Span(text=body, bbox=(40.0, 100.0, 500.0, 120.0), page=1, font="Arial", size=10.0),
            Span(text=footer, bbox=(40.0, 760.0, 200.0, 780.0), page=1, font="Arial", size=8.0),
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
    assert total == 44


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

    assert valid.pages[0].page_type == HIGHLIGHTS_PAGE_TYPE
    assert valid_results[0].status == "PASS"
    assert valid_suggestions == []
    assert invalid_results[0].status == "FAIL"
    assert len(invalid_suggestions) == 1
    assert invalid_suggestions[0].original == "REVISION No. 05 DATED JUL 27/26"
    assert invalid_suggestions[0].proposed == "REVISION No. 04 DATED JUL 27/26"
    assert invalid_suggestions[0].bbox == (40.0, 756.0, 300.0, 766.0)
    assert missing_results[0].status == "FAIL"


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
