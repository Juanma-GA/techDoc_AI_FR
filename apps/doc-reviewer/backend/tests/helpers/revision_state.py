"""Shared builders for the revision state tests (synthetic spans, LEP / Highlights / ROR pages)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.checks.client_registry import load_active_client_configuration
from app.checks.thales_rules.ata100 import revision_engine as revision
from app.checks.thales_rules.ata100.rules import REVISION_RULE_DEFINITIONS
from app.core.compiled_rule_executor import execute_pdf_rules as _execute_pdf_rules
from app.parsers.pdf_parser import (
    ParsedPage,
    ParsedPdf,
    PdfWord,
    Span,
)


_TEST_CLIENT_BUNDLE = load_active_client_configuration().bundle


_REVISION_RULES = [
    definition.compiled_rule for definition in REVISION_RULE_DEFINITIONS
]


def execute_pdf_rules(*args: Any, **kwargs: Any):
    kwargs.setdefault("client_operations", _TEST_CLIENT_BUNDLE.operations)
    kwargs.setdefault("client_entities", _TEST_CLIENT_BUNDLE.mapping.entities)
    return _execute_pdf_rules(*args, **kwargs)


_COPYRIGHT = (
    "\u00a9 1966-2026 THALES AVS FRANCE SAS. This document and any data included "
    "are the property of THALES AVS FRANCE SAS."
)


_REVISION_DATE = "JUL 27/26"


_DOCUMENT = SimpleNamespace(
    meta_revision_date=_REVISION_DATE,
    meta_first_issue_date="JUL 1966",
    meta_last_issue_date="MAR 77",
)


def _span(text: str, x: float, y: float, page: int) -> Span:
    return Span(
        text=text,
        bbox=(x, y - 5.0, x + 6.0 * len(text), y + 5.0),
        page=page,
        font="Arial",
        size=10.0,
    )


def _word(text: str, x_position: float, center_y: float, word_index: int) -> PdfWord:
    return PdfWord(
        text=text,
        bbox=(
            x_position,
            center_y - 5.0,
            x_position + 6.0 * len(text),
            center_y + 5.0,
        ),
        block_index=0,
        line_index=0,
        word_index=word_index,
    )


def _footer(page: int, label: str, date: str, y: float = 756.0) -> list[Span]:
    return [
        _span(_COPYRIGHT, 85.9, y, page),
        _span(label, 500.0, y, page),
        _span(date, 507.0, y + 16.0, page),
    ]


def _page(page: int, spans: list[Span]) -> ParsedPage:
    return ParsedPage(
        page=page,
        text="\n".join(span.text for span in spans),
        spans=spans,
    )


def _ror_page(revision_date: str, insertion_date: str, page: int = 1) -> ParsedPage:
    spans = [
        _span("RECORD OF REVISIONS", 100.0, 100.0, page),
        _span("REVISION DATE", 200.0, 140.0, page),
        _span("INSERTION DATE", 350.0, 140.0, page),
        _span(revision_date, 200.0, 170.0, page),
        _span(insertion_date, 350.0, 170.0, page),
    ]
    return _page(page, spans)


def _highlights_page(rows: list[tuple[str, str, str]], page: int = 1) -> ParsedPage:
    """One (subject, page range, status) block per row, laid out like the PDF."""
    spans = [
        _span("HIGHLIGHTS", 293.9, 137.6, page),
        _span("Chapter/Section and Page No", 105.8, 229.3, page),
        _span("Designation", 292.0, 229.3, page),
        _span("Description of Change", 399.0, 229.3, page),
    ]
    y = 250.0
    for subject, pages_text, status in rows:
        spans.append(_span(subject, 90.7, y, page))
        spans.append(_span(pages_text, 90.7, y + 14.0, page))
        if status:
            spans.append(_span(status, 322.2, y + 14.0, page))
        spans.append(_span("Updated.", 366.4, y + 14.0, page))
        y += 42.0
    spans.extend(_footer(page, "Highlights Page 1", _REVISION_DATE))
    return _page(page, spans)


def _lep_page(
    left: list[tuple[str, str, str]],
    right: list[tuple[str, str, str]],
    page: int = 2,
    columns: tuple[tuple[float, float, float, float], ...] = (
        (86.4, 114.7, 194.2, 249.5),
        (329.4, 357.0, 435.4, 492.1),
    ),
) -> ParsedPage:
    """`left`/`right` hold (subject, page id, date) for each column group.

    An entry with an empty page id renders a subject-only row, which is how
    the real table wraps a long section name over two lines. `columns` gives
    the (subject, prefix, page, date) abscissa of each group.
    """
    spans = [_span("LIST OF EFFECTIVE PAGES", 254.9, 95.1, page)]
    for subject_x, _prefix_x, page_x, date_x in columns:
        spans.append(_span("SUBJECT", subject_x, 122.2, page))
        spans.append(_span("PAGE", page_x + 0.2, 122.2, page))
        spans.append(_span("DATE", date_x + 7.9, 122.2, page))
    for group, (subject_x, prefix_x, page_x, date_x) in zip((left, right), columns):
        y = 151.0
        for subject, page_id, date in group:
            if subject:
                spans.append(_span(subject, subject_x, y, page))
            if page_id:
                prefix, _, number = page_id.rpartition(" ")
                if prefix:
                    spans.append(_span(prefix, prefix_x, y, page))
                spans.append(_span(number, page_x, y, page))
                spans.append(_span(date, date_x, y, page))
            y += 14.3
    spans.extend(_footer(page, "LEP Page 1", _REVISION_DATE))
    return _page(page, spans)


def _document(pages: list[ParsedPage]) -> ParsedPdf:
    return ParsedPdf(
        page_count=len(pages),
        pages=pages,
        full_text="\n".join(page.text for page in pages),
        is_signed=False,
    )


def _consistent_document() -> ParsedPdf:
    return _document(
        [
            _highlights_page(
                [
                    ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
                    ("Repair", "Pages 401 to 402", "R"),
                ]
            ),
            _lep_page(
                left=[
                    ("List of Effec-", "", ""),
                    ("tive Pages", "", ""),
                    ("", "LEP 1", f"{_REVISION_DATE} *"),
                    ("", "LEP 2", "Blank     *"),
                    ("Repair", "401", f"{_REVISION_DATE} *"),
                    ("", "402", f"{_REVISION_DATE} *"),
                ],
                right=[("Assembly", "501", "JUL 66")],
            ),
            _page(3, _footer(3, "Page 401", _REVISION_DATE)),
            _page(4, _footer(4, "Page 402", _REVISION_DATE)),
            _page(5, _footer(5, "Page 501", "JUL 66")),
        ]
    )


def _lep_with(
    *rows: tuple[str, str, str],
    right: tuple[str, str, str] = ("Assembly", "501", "JUL 66"),
    columns: tuple[tuple[float, float, float, float], ...] | None = None,
) -> ParsedPage:
    """Rebuild the LEP page, keeping the two entries describing itself."""
    left = [
        ("List of Effec-", "", ""),
        ("tive Pages", "", ""),
        ("", "LEP 1", f"{_REVISION_DATE} *"),
        ("", "LEP 2", "Blank     *"),
        *rows,
    ]
    if columns is None:
        return _lep_page(left=left, right=[right])
    return _lep_page(left=left, right=[right], columns=columns)


def _state(parsed: ParsedPdf, document: object = _DOCUMENT) -> revision.RevisionState:
    return revision.build_revision_state(parsed, document)


def _findings(
    parsed: ParsedPdf, document: object = _DOCUMENT
) -> list[revision.RevisionFinding]:
    return _state(parsed, document).findings


def _codes(parsed: ParsedPdf, document: object = _DOCUMENT) -> list[str]:
    return [finding.control for finding in _findings(parsed, document)]
