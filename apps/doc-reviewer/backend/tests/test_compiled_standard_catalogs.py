"""Coverage for the built-in standards expressed as CompiledRule."""

from __future__ import annotations

from types import SimpleNamespace

from app.checks.standards import BUILTIN_STANDARDS, serialize_builtin_version

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
    assert total == 39


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
        ("79-33-02", "79-30-02")
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
        ("JUL 27/25", "JUL 27/26")
    ]
    assert missing[0].status == "FAIL"
    assert missing_suggestions == []


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
    assert missing_suggestions == []


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
