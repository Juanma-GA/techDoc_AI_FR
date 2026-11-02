"""Shared builders for the compiled standard catalog tests (synthetic PDFs, rule lookup)."""

from __future__ import annotations

from typing import Any

from app.checks.client_registry import load_active_client_configuration
from app.checks.standards import BUILTIN_STANDARDS
from app.checks.thales_rules.ata100.page_classifier import TP2_PAGE_TYPE
from app.core.compiled_rule_executor import execute_pdf_rules as _execute_pdf_rules
from app.core.compiled_rules import CompiledRule
from app.parsers.pdf_parser import (
    ParsedPage,
    ParsedPdf,
    PdfLine,
    Span,
)


_TEST_CLIENT_BUNDLE = load_active_client_configuration().bundle


def execute_pdf_rules(*args: Any, **kwargs: Any):
    kwargs.setdefault("client_operations", _TEST_CLIENT_BUNDLE.operations)
    kwargs.setdefault("client_entities", _TEST_CLIENT_BUNDLE.mapping.entities)
    return _execute_pdf_rules(*args, **kwargs)


def _rule(code: str) -> CompiledRule:
    for spec in BUILTIN_STANDARDS:
        for label in spec["versions"]:
            for rule in spec["versions"][label]:
                if rule.id == code:
                    return rule
    for definition in _TEST_CLIENT_BUNDLE.rules:
        if definition.code == code:
            return definition.compiled_rule
    raise AssertionError(f"Unknown built-in rule: {code}")


def _pdf(text: str) -> ParsedPdf:
    page = ParsedPage(page=1, text=text, spans=[])
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def _two_row_table_pdf(rows: list[tuple[str, str]]) -> ParsedPdf:
    lines: list[str] = []
    spans: list[Span] = []
    for row_index, (left, right) in enumerate(rows):
        y = 200.0 + row_index * 20.0
        lines.append(f"{left} {right}")
        spans.extend(
            [
                Span(left, (40.0, y, 220.0, y + 12.0), 1, "Arial", 10.0),
                Span(right, (280.0, y, 500.0, y + 12.0), 1, "Arial", 10.0),
            ]
        )
    text = "\n".join(lines)
    page = ParsedPage(
        page=1,
        text=text,
        spans=spans,
        is_modified=True,
        page_height=792.0,
    )
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def _numbered_chapter_pdf(pages: list[tuple[str, list[str]]]) -> ParsedPdf:
    parsed_pages = []
    for physical_page, (page_key, headings) in enumerate(pages, start=1):
        spans = []
        lines = []
        for index, heading in enumerate(headings):
            y = 130.0 + index * 24.0
            bbox = (86.0, y, 500.0, y + 14.0)
            lines.append(PdfLine(heading, bbox, block_index=1, line_index=index))
            spans.append(Span(heading, bbox, physical_page, "Arial", 12.0))
        spans.extend(
            [
                Span("THALES AVS FRANCE SAS", (85.0, 755.0, 220.0, 765.0), physical_page, "Arial", 9.0),
                Span(f"Page {page_key}", (500.0, 755.0, 560.0, 765.0), physical_page, "Arial", 9.0),
                Span("JUL 27/26", (500.0, 771.0, 560.0, 781.0), physical_page, "Arial", 9.0),
            ]
        )
        text = "\n".join([*headings, "THALES AVS FRANCE SAS", f"Page {page_key}", "JUL 27/26"])
        parsed_pages.append(
            ParsedPage(
                page=physical_page,
                text=text,
                spans=spans,
                lines=lines,
                page_height=792.0,
            )
        )
    full_text = "\n".join(page.text for page in parsed_pages)
    return ParsedPdf(
        page_count=len(parsed_pages),
        pages=parsed_pages,
        full_text=full_text,
        is_signed=False,
    )


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


def _note_page_pdf(text: str, page_type: str) -> ParsedPdf:
    page = ParsedPage(page=1, text=text, page_type=page_type)
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)
