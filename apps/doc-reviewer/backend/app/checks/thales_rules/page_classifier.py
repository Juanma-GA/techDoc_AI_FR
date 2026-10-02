"""THALES page classification and per-page analysis initialization."""

from __future__ import annotations

import re

from . import revision_engine as revision
from .operations import revision_state
from app.core.logging import get_logger
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


_logger = get_logger(__name__)

TP1_PAGE_TYPE = "TP1"
TP2_PAGE_TYPE = "TP2"
HIGHLIGHTS_PAGE_TYPE = "HIGHLIGHTS"
HIGHLIGHTS_FIRST_PAGE_TYPE = "HIGHLIGHTS_PAGE_1"
INTRODUCTION_PAGE_TYPE = "INTRODUCTION"
REPAIR_PAGE_TYPE = "REPAIR"
TESTING_PAGE_TYPE = "TESTING"
STORAGE_PAGE_TYPE = "STORAGE"

_NOTE_PAGE_TYPES = (REPAIR_PAGE_TYPE, TESTING_PAGE_TYPE, STORAGE_PAGE_TYPE)
_PAGE_TYPE_MARKERS = {
    page_type: re.compile(rf"(?im)^\s*(?:\d+(?:\.\d+)*[.)]?\s+)?{page_type}\s*$")
    for page_type in _NOTE_PAGE_TYPES
}
_HIGHLIGHTS_PAGE_1_MARKER = re.compile(r"(?i)\bHighlights\s+Page\s+1\b")
_INTRODUCTION_PAGE_MARKER = re.compile(r"(?m)^\s*INTRODUCTION\s*$")
_TABLE_OF_CONTENTS_MARKER = re.compile(r"(?im)^\s*TABLE\s+OF\s+CONTENTS\s*$")
_HIGHLIGHTS_PAGE_TYPES = [HIGHLIGHTS_PAGE_TYPE, HIGHLIGHTS_FIRST_PAGE_TYPE]
_FOOTER_BAND_MIN_HEIGHT = 80.0
_FOOTER_LINE_TOLERANCE = 3.0
_CMM_NUMBER_PATTERN = r"\d{2}-\d{2}-\d{2}"


def _normalized_line(value: str) -> str:
    return " ".join(value.split()).strip()


def _footer_lines(page: ParsedPage) -> list[str]:
    if not page.spans:
        return []
    min_y = min(span.bbox[1] for span in page.spans)
    max_y = max(span.bbox[3] for span in page.spans)
    footer_top = max_y - max((max_y - min_y) * 0.25, _FOOTER_BAND_MIN_HEIGHT)
    footer_spans = [span for span in page.spans if span.bbox[3] >= footer_top]
    groups: list[tuple[float, list[str]]] = []
    for span in sorted(footer_spans, key=lambda item: (item.bbox[1], item.bbox[0])):
        center_y = (span.bbox[1] + span.bbox[3]) / 2
        if groups and abs(center_y - groups[-1][0]) <= _FOOTER_LINE_TOLERANCE:
            groups[-1][1].append(span.text)
        else:
            groups.append((center_y, [span.text]))
    return [_normalized_line(" ".join(parts)) for _center_y, parts in groups]


def _footer_has_structural_anchor(lines: list[str]) -> bool:
    footer_text = " ".join(lines)
    return bool(
        re.search(_CMM_NUMBER_PATTERN, footer_text)
        or any(revision.parse_date(line) is not None for line in lines)
    )


def identify_page_type(
    parsed: ParsedPdf,
    page_name: str,
    revision_date: str | None,
    cmm_number: str | None = None,
) -> dict[str, str | None]:
    """Classify pages by footer anchors and a requested page-type marker."""
    expected_anchors = [
        _normalized_line(cmm_number or "").casefold(),
        _normalized_line(revision_date or "").casefold(),
    ]
    page_marker = r"\s*".join(re.escape(character) for character in page_name)
    page_marker_pattern = re.compile(rf"\b{page_marker}\b", re.IGNORECASE)
    expected_anchors = [anchor for anchor in expected_anchors if anchor]
    if not expected_anchors:
        _logger.warning(
            "tp1_detection_skipped_no_anchor",
            reason="meta_cmm_number et meta_revision_date absents du contexte document",
        )

    page_types: dict[str, str | None] = {}
    for page in parsed.pages:
        lines = _footer_lines(page)
        footer_text = " ".join(lines).casefold()
        has_anchor = _footer_has_structural_anchor(lines) or any(
            anchor in footer_text for anchor in expected_anchors
        )
        has_marker = bool(page_marker_pattern.search(footer_text))
        if has_anchor and has_marker:
            page.page_type = page_name
            if (
                page_name == HIGHLIGHTS_PAGE_TYPE
                and _HIGHLIGHTS_PAGE_1_MARKER.search(page.text)
            ):
                page.page_type = HIGHLIGHTS_FIRST_PAGE_TYPE
        elif page.page_type == page_name or (
            page_name == HIGHLIGHTS_PAGE_TYPE
            and page.page_type in _HIGHLIGHTS_PAGE_TYPES
        ):
            page.page_type = None
        if expected_anchors and page.page_type != page_name:
            _logger.debug(
                "tp1_detection_no_match",
                page=page.page,
            )
        page_types[str(page.page)] = page.page_type
    return page_types


def identify_tp1_pages(
    parsed: ParsedPdf,
    revision_date: str | None,
    cmm_number: str | None = None,
) -> dict[str, str | None]:
    """Backward-compatible TP1-specific wrapper."""
    return identify_page_type(parsed, TP1_PAGE_TYPE, revision_date, cmm_number)


def identify_note_pages(parsed: ParsedPdf) -> dict[str, str | None]:
    """Classify NOTE pages from a standalone REPAIR/TESTING/STORAGE heading."""
    page_types: dict[str, str | None] = {}
    for page in parsed.pages:
        if revision._is_lep_page(page) or _TABLE_OF_CONTENTS_MARKER.search(page.text or ""):
            if page.page_type in _NOTE_PAGE_TYPES:
                page.page_type = None
            page_types[str(page.page)] = page.page_type
            continue
        detected_types = [
            page_type
            for page_type, marker in _PAGE_TYPE_MARKERS.items()
            if marker.search(page.text)
        ]
        detected_type = detected_types[0] if len(detected_types) == 1 else None
        if detected_type is not None and (
            page.page_type is None or page.page_type in _NOTE_PAGE_TYPES
        ):
            page.page_type = detected_type
        elif page.page_type in _NOTE_PAGE_TYPES:
            page.page_type = None
        page_types[str(page.page)] = page.page_type
    return page_types


def identify_introduction_pages(parsed: ParsedPdf) -> dict[str, str | None]:
    """Classify pages carrying the standalone INTRODUCTION heading."""
    page_types: dict[str, str | None] = {}
    for page in parsed.pages:
        if page.page_type is None or page.page_type == INTRODUCTION_PAGE_TYPE:
            if (
                _INTRODUCTION_PAGE_MARKER.search(page.text or "")
                and _TABLE_OF_CONTENTS_MARKER.search(page.text or "") is None
            ):
                page.page_type = INTRODUCTION_PAGE_TYPE
            elif page.page_type == INTRODUCTION_PAGE_TYPE:
                page.page_type = None
        page_types[str(page.page)] = page.page_type
    return page_types


def classify_pages(parsed: ParsedPdf, document: object) -> None:
    """Classify page types and initialize the document's revision state."""
    identify_tp1_pages(
        parsed,
        getattr(document, "meta_revision_date", None),
        getattr(document, "meta_cmm_number", None),
    )
    identify_page_type(
        parsed,
        TP2_PAGE_TYPE,
        getattr(document, "meta_revision_date", None),
        getattr(document, "meta_cmm_number", None),
    )
    identify_page_type(
        parsed,
        HIGHLIGHTS_PAGE_TYPE,
        getattr(document, "meta_revision_date", None),
        getattr(document, "meta_cmm_number", None),
    )
    identify_note_pages(parsed)
    identify_introduction_pages(parsed)
    revision_state(parsed, document)


__all__ = [
    "HIGHLIGHTS_FIRST_PAGE_TYPE",
    "HIGHLIGHTS_PAGE_TYPE",
    "INTRODUCTION_PAGE_TYPE",
    "REPAIR_PAGE_TYPE",
    "STORAGE_PAGE_TYPE",
    "TESTING_PAGE_TYPE",
    "TP1_PAGE_TYPE",
    "TP2_PAGE_TYPE",
    "classify_pages",
    "identify_introduction_pages",
    "identify_note_pages",
    "identify_page_type",
    "identify_tp1_pages",
]