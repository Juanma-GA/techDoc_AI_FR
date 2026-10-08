from __future__ import annotations

import fitz
from types import SimpleNamespace

from app.checks.thales_rules import operations
from app.checks.thales_rules.revision_engine import HighlightsEntry, RevisionState
from app.checks.thales_rules.rules import (
    CUSTOM_REVISION_BAR_MODIFIED_PAGE,
    CUSTOM_REVISION_BAR_NEW_PAGE,
)
from app.core.compiled_rule_executor import execute_pdf_rules
from app.parsers.pdf_parser import (
    ParsedPage,
    ParsedPdf,
    PdfVectorPrimitive,
    Span,
    parse_pdf,
)


def test_pdf_parser_preserves_black_vector_revision_bar_without_ocr() -> None:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.draw_line((75.6, 115.8), (75.6, 661.45), color=(0, 0, 0), width=2.28)
    payload = document.tobytes()
    document.close()

    parsed = parse_pdf(payload)
    primitives = parsed.pages[0].vector_primitives

    assert parsed.pages[0].page_width == 612.0
    assert any(
        primitive.kind == "line"
        and primitive.color == (0.0, 0.0, 0.0)
        and abs(primitive.width - 2.28) < 0.01
        and all(
            abs(actual - expected) < 0.01
            for actual, expected in zip(
                primitive.bbox,
                (75.6, 115.8, 75.6, 661.45),
                strict=True,
            )
        )
        for primitive in primitives
    )


def _bar(x: float, top: float, bottom: float) -> PdfVectorPrimitive:
    return PdfVectorPrimitive(
        kind="line",
        bbox=(x, top, x, bottom),
        color=(0.0, 0.0, 0.0),
        fill=None,
        width=2.28,
    )


def _context(
    status: str,
    bars: list[PdfVectorPrimitive],
    *,
    page_number: int = 1,
    page_type: str | None = None,
    spans: list[Span] | None = None,
) -> SimpleNamespace:
    page_key = "TP 2" if page_type == "TP2" else f"TEST {page_number}"
    page = ParsedPage(
        page=page_number,
        text="\n".join(span.text for span in spans or []),
        spans=spans or [],
        page_type=page_type,
        page_width=612.0,
        page_height=792.0,
        vector_primitives=bars,
    )
    parsed = ParsedPdf(
        page_count=page_number,
        pages=[page],
        full_text=page.text,
        is_signed=False,
    )
    revision_state = RevisionState(
        highlights=[
            HighlightsEntry(
                subject="Test",
                pages_text=page_key,
                page_keys=(page_key,),
                status=status,
                page=page_number,
                bbox=(0.0, 0.0, 0.0, 0.0),
                status_bbox=(0.0, 0.0, 0.0, 0.0),
            )
        ],
        expected_footer_keys={page_number: page_key},
    )
    setattr(parsed, operations._REVISION_STATE_ATTR, revision_state)
    return SimpleNamespace(
        runtime=SimpleNamespace(parsed_pdf=parsed, document=None, is_docx=False),
        targets=(),
    )


def _execute(control: str, context: SimpleNamespace):
    return operations.DOCUMENT_STRUCTURE.execute(context, {"control": control})


def test_new_revision_page_requires_a_near_full_height_bar() -> None:
    valid = _execute("revision_bar_new", _context("N", [_bar(75.6, 14.0, 778.0)]))
    invalid = _execute("revision_bar_new", _context("N", [_bar(75.6, 180.0, 500.0)]))

    assert valid.status == "PASS"
    assert invalid.status == "FAIL"


def test_modified_revision_page_requires_at_least_one_bar() -> None:
    valid = _execute("revision_bar_modified", _context("R", [_bar(75.6, 180.0, 300.0)]))
    invalid = _execute("revision_bar_modified", _context("R", []))

    assert valid.status == "PASS"
    assert invalid.status == "FAIL"


def test_revision_bar_offset_matches_margin_on_odd_and_even_pages() -> None:
    odd = _execute(
        "revision_bar_margin",
        _context("R", [_bar(75.6, 180.0, 300.0)], page_number=1),
    )
    even = _execute(
        "revision_bar_margin",
        _context("N", [_bar(39.65, 14.0, 778.0)], page_number=2),
    )
    misplaced = _execute(
        "revision_bar_margin",
        _context("R", [_bar(90.0, 180.0, 300.0)], page_number=1),
    )

    assert odd.status == "PASS"
    assert even.status == "PASS"
    assert misplaced.status == "FAIL"


def test_tp2_modified_bar_must_overlap_body_text_outside_header_and_footer() -> None:
    spans = [
        Span("T", (50.0, 14.0, 70.0, 45.0), 1, "Arial-Bold", 30.0),
        Span("Modified text", (100.0, 200.0, 300.0, 220.0), 1, "Arial", 10.0),
        Span("THALES AVS FRANCE SAS", (50.0, 750.0, 250.0, 763.0), 1, "Arial", 9.0),
        Span("TP 2", (500.0, 750.0, 560.0, 763.0), 1, "Arial", 9.0),
    ]
    body_bar = _execute(
        "revision_bar_tp2_body",
        _context("R", [_bar(39.65, 195.0, 225.0)], page_type="TP2", spans=spans),
    )
    header_bar = _execute(
        "revision_bar_tp2_body",
        _context("R", [_bar(39.65, 14.0, 60.0)], page_type="TP2", spans=spans),
    )
    footer_bar = _execute(
        "revision_bar_tp2_body",
        _context("R", [_bar(39.65, 740.0, 775.0)], page_type="TP2", spans=spans),
    )

    assert body_bar.status == "PASS"
    assert header_bar.status == "FAIL"
    assert footer_bar.status == "FAIL"


def test_tp2_new_page_is_not_applicable_to_the_tp2_modified_bar_rule() -> None:
    result = _execute("revision_bar_tp2_body", _context("N", [], page_type="TP2"))

    assert result.status == "PASS"


def test_compiled_bar_rules_emit_suggestions_for_every_failing_page(monkeypatch) -> None:
    page_keys = ("INTRO 1101 3", "INTRO 1101 4", "1101 1", "1102 1")
    statuses = ("N", "N", "R", "R")
    pages = [
        ParsedPage(
            page=65 + index,
            text=f"Page {page_key}",
            page_width=612.0,
            page_height=792.0,
        )
        for index, page_key in enumerate(page_keys)
    ]
    parsed = ParsedPdf(
        page_count=68,
        pages=pages,
        full_text="\n".join(page.text for page in pages),
        is_signed=False,
    )
    state = RevisionState(
        highlights=[
            HighlightsEntry(
                subject="Test",
                pages_text=page_key,
                page_keys=(page_key,),
                status=status,
                page=index + 1,
                bbox=(0.0, 0.0, 1.0, 1.0),
                status_bbox=(0.0, 0.0, 1.0, 1.0),
            )
            for index, (page_key, status) in enumerate(
                zip(page_keys, statuses, strict=True)
            )
        ],
        expected_footer_keys={
            page.page: page_key
            for page, page_key in zip(pages, page_keys, strict=True)
        },
    )
    monkeypatch.setattr(operations, "revision_state", lambda _parsed, _document: state)

    results, suggestions = execute_pdf_rules(
        parsed,
        [
            CUSTOM_REVISION_BAR_NEW_PAGE.compiled_rule,
            CUSTOM_REVISION_BAR_MODIFIED_PAGE.compiled_rule,
        ],
        client_operations=operations.OPERATIONS,
    )

    assert [result.status for result in results] == ["FAIL", "FAIL"]
    assert [
        item.page
        for item in suggestions
        if item.rule_code == CUSTOM_REVISION_BAR_NEW_PAGE.code
    ] == [65, 66]
    assert [
        item.page
        for item in suggestions
        if item.rule_code == CUSTOM_REVISION_BAR_MODIFIED_PAGE.code
    ] == [67, 68]
    assert len(suggestions) == 4
    assert all(item.original == "" and item.bbox is not None for item in suggestions)