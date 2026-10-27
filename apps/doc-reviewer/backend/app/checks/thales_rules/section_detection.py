"""THALES preparation: section detection from the 11 documented checks.

Each page is read for independent signal families (footer label / number range,
title line, table or content cues, position in the Highlights -> TP1 sequence).
Two families agreeing confirm a section; one family only leaves it partial;
signals pointing at different sections are a conflict and stay unclassified.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.parsers.pdf_parser import ParsedPage, ParsedPdf

from . import revision_engine as revision
from .page_classifier import (
    HIGHLIGHTS_FIRST_PAGE_TYPE,
    HIGHLIGHTS_PAGE_TYPE,
    TP1_PAGE_TYPE,
)
from .page_classifier import _footer_lines as footer_lines

ROR = "ROR"
LEP = "LEP"
INTRODUCTION = "INTRODUCTION"
TESTING = "TESTING"
REPAIR = "REPAIR"
ASSEMBLY = "ASSEMBLY"
SPECIAL_TOOLS = "SPECIAL_TOOLS"
VENDOR_CODE_LIST = "VENDOR_CODE_LIST"
TABLE_OF_CONTENTS = "TABLE_OF_CONTENTS"

SECTION_PAGE_TYPES = (
    HIGHLIGHTS_PAGE_TYPE,
    TP1_PAGE_TYPE,
    ROR,
    LEP,
    INTRODUCTION,
    TESTING,
    REPAIR,
    ASSEMBLY,
    SPECIAL_TOOLS,
    VENDOR_CODE_LIST,
    TABLE_OF_CONTENTS,
)

FOOTER = "footer"
TITLE = "title"
CONTENT = "content"
POSITION = "position"

_HIGHLIGHTS_TYPES = {HIGHLIGHTS_PAGE_TYPE, HIGHLIGHTS_FIRST_PAGE_TYPE}
_NUMBER_RANGES = (
    (TESTING, 101, 199),
    (REPAIR, 601, 699),
    (ASSEMBLY, 701, 799),
    (SPECIAL_TOOLS, 901, 999),
    (VENDOR_CODE_LIST, 1001, 1999),
)
_FOOTER_LABELS = (
    (HIGHLIGHTS_PAGE_TYPE, re.compile(r"(?i)\bHigh?lights?\s+Page\s+(\d+)")),
    (TP1_PAGE_TYPE, re.compile(r"(?i)\bTP(?:\s+Page\s+|\s*-\s*)(\d+)")),
    (ROR, re.compile(r"(?i)\b(?:ROR\s+Page\s+|RR\s*-\s*)(\d+)")),
    (LEP, re.compile(r"(?i)\b(?:LEP\s+Page\s+|LEP\s*-\s*)(\d+)")),
    (INTRODUCTION, re.compile(r"(?i)\b(?:INTRO\s+Page\s+|INTRO\s*-\s*)(\d+)")),
    (TABLE_OF_CONTENTS, re.compile(r"(?i)\b(?:TC\s+Page\s+|TC\s*-\s*)(\d+)")),
    (SPECIAL_TOOLS, re.compile(r"(?i)\b(?:LM\s+Page\s+|LM\s*-\s*)(\d+)")),
)
_NUMBERED = r"(?:\d+(?:\.\d+)*[.)]?\s+)?"
_TITLES = {
    TESTING: r"TESTING(?:\s+AND\s+FAULT\s+ISOLATION)?",
    REPAIR: r"REPAIR",
    ASSEMBLY: (
        r"ASSEMBLY(?:\s+AND\s+STORAGE|\s+INCLUDING\s+STORAGE"
        r"|\s+\(\s*INCLUDING\s+STORAGE\s*\))?"
    ),
    VENDOR_CODE_LIST: r"VENDOR\s+CODE\s+LIST",
    TABLE_OF_CONTENTS: r"TABLE\s+OF\s+CONTENTS",
    INTRODUCTION: r"INTRODUCTION",
    ROR: r"RECORD\s+OF\s+REVISIONS",
    LEP: r"LIST\s+OF\s+EFFECTIVE\s+PAGES",
}
_TITLE_RES = {
    section: re.compile(rf"(?i){_NUMBERED}{pattern}") for section, pattern in _TITLES.items()
}
_SPECIAL_TOOLS_TITLE_RE = re.compile(
    r"(?i)(?:consumables|list\s+of\s+consumables(?:\s*\(\s*cont[’']?d\.?\s*\))?"
    r"|list\s+of\s+materials|materials)"
)
_HIGHLIGHTS_HEADERS = (
    re.compile(r"(?i)chapter\s*/\s*section"),
    re.compile(r"(?i)\bdesignation\b"),
    re.compile(r"(?i)description\s+of\s+change"),
)
_HIGHLIGHTS_REVISION_RE = re.compile(r"(?i)\brevision\s+no\.?\s*\S+\s+dated\s+\S+")
_ROR_HEADERS = (
    re.compile(r"(?i)\brev\.?\s*no\b"),
    re.compile(r"(?i)\brevision\s+date\b"),
    re.compile(r"(?i)\binsertion\s+date\b"),
    re.compile(r"(?i)(?:^|\s)by(?:\s|$)"),
)
_LEP_HEADERS = tuple(re.compile(rf"(?im)^\W*{word}\W*$") for word in ("subject", "page", "date"))
_LEP_HEADER_LINE_RE = re.compile(r"(?i)\bsubject\b.*\bpage\b.*\bdate\b")
_PAGE_NUMBER_LINE_RE = re.compile(r"(?i)(?:page\s+)?(\d{3,4})")
_TABLE_PRIMITIVE_MIN = 4


@dataclass(frozen=True)
class SectionSignal:
    section: str
    family: str
    detail: str
    number: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"section": self.section, "family": self.family, "detail": self.detail}


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _text_lines(page: ParsedPage) -> list[str]:
    lines = []
    for raw in (page.text or "").splitlines():
        line = " ".join(re.sub(r"^[#>*\-\s|]+|[*|\s]+$", "", raw).split())
        if line:
            lines.append(line)
    return lines


def _footer_signals(page: ParsedPage) -> list[SectionSignal]:
    signals: list[SectionSignal] = []
    lines = footer_lines(page)
    for line in lines:
        for section, pattern in _FOOTER_LABELS:
            match = pattern.search(line)
            if match is None:
                continue
            number = int(match.group(1))
            if section == TP1_PAGE_TYPE and number != 1:
                continue
            signals.append(SectionSignal(section, FOOTER, f"label: {line}", number))
    numbers = {
        int(match.group(1))
        for line in lines
        if (match := _PAGE_NUMBER_LINE_RE.fullmatch(line)) is not None
    }
    footer = revision.extract_footer(page)
    key = footer.page_key if footer is not None else None
    if key is not None and revision.page_key_prefix(key) == "":
        number = revision.page_number_of(key)
        if number is not None:
            numbers.add(number)
    for number in sorted(numbers):
        for section, low, high in _NUMBER_RANGES:
            if low <= number <= high:
                signals.append(SectionSignal(section, FOOTER, f"page number {number}", number))
    return signals


def _title_signals(page: ParsedPage) -> list[SectionSignal]:
    signals: list[SectionSignal] = []
    for line in _text_lines(page):
        for section, pattern in _TITLE_RES.items():
            if pattern.fullmatch(line):
                signals.append(SectionSignal(section, TITLE, f"title: {line}"))
        if _SPECIAL_TOOLS_TITLE_RE.fullmatch(line):
            signals.append(SectionSignal(SPECIAL_TOOLS, TITLE, f"sub-section: {line}"))
    return signals


def _content_signals(page: ParsedPage, metadata: Mapping[str, Any]) -> list[SectionSignal]:
    text = page.text or ""
    lines = _text_lines(page)
    signals: list[SectionSignal] = []
    if all(pattern.search(text) for pattern in _HIGHLIGHTS_HEADERS):
        revision_line = _HIGHLIGHTS_REVISION_RE.search(text)
        detail = "table: Chapter/Section, Designation, Description of Change"
        if revision_line:
            detail += f"; {revision_line.group(0)}"
        signals.append(SectionSignal(HIGHLIGHTS_PAGE_TYPE, CONTENT, detail))
    if sum(1 for pattern in _ROR_HEADERS if any(pattern.search(line) for line in lines)) >= 3:
        signals.append(
            SectionSignal(ROR, CONTENT, "columns: REV. No., REVISION DATE, INSERTION DATE, BY")
        )
    if _LEP_HEADER_LINE_RE.search(text) or all(pattern.search(text) for pattern in _LEP_HEADERS):
        signals.append(SectionSignal(LEP, CONTENT, "columns: SUBJECT, PAGE, DATE"))
    cmm = str(metadata.get("meta_cmm_number") or "")
    first_issue = str(metadata.get("meta_first_issue_date") or "")
    normalized = _norm(text)
    if cmm and first_issue and _norm(cmm) in normalized and _norm(first_issue) in normalized:
        signals.append(
            SectionSignal(TP1_PAGE_TYPE, CONTENT, "mapping: CMM number and first issue found")
        )
    primitives = sum(1 for item in page.vector_primitives if item.kind in {"line", "rect"})
    if primitives >= _TABLE_PRIMITIVE_MIN and any(
        _SPECIAL_TOOLS_TITLE_RE.fullmatch(line) for line in lines
    ):
        signals.append(
            SectionSignal(SPECIAL_TOOLS, CONTENT, f"table present ({primitives} primitives)")
        )
    return signals


def detect_section_signals(page: ParsedPage, metadata: Mapping[str, Any]) -> list[SectionSignal]:
    signals = _footer_signals(page) + _title_signals(page) + _content_signals(page, metadata)
    titles = {signal.section for signal in signals if signal.family == TITLE}
    # LEP and table-of-contents pages list every other section title as a line.
    owner = LEP if LEP in titles else TABLE_OF_CONTENTS if TABLE_OF_CONTENTS in titles else None
    if owner is not None:
        signals = [
            signal for signal in signals if signal.family != TITLE or signal.section == owner
        ]
    # Consumables/Materials headings are generic: a footer naming another section wins.
    footer_sections = {signal.section for signal in signals if signal.family == FOOTER}
    if footer_sections and SPECIAL_TOOLS not in footer_sections:
        signals = [
            signal
            for signal in signals
            if signal.section != SPECIAL_TOOLS or signal.family == FOOTER
        ]
    return signals


def _resolve(
    signals: list[SectionSignal],
    legacy_type: str | None,
) -> tuple[str | None, str, list[str]]:
    sections = sorted({signal.section for signal in signals})
    if len(sections) > 1:
        return None, "conflict", sections
    if not sections:
        return (legacy_type, "detected", []) if legacy_type else (None, "unclassified", [])
    section = sections[0]
    if legacy_type is not None and legacy_type != section and not (
        section == HIGHLIGHTS_PAGE_TYPE and legacy_type in _HIGHLIGHTS_TYPES
    ):
        return None, "conflict", sorted({section, legacy_type})
    families = {signal.family for signal in signals}
    status = "confirmed" if len(families) >= 2 else "partial"
    if section == HIGHLIGHTS_PAGE_TYPE:
        first = legacy_type == HIGHLIGHTS_FIRST_PAGE_TYPE or any(
            signal.family == FOOTER and signal.number == 1 for signal in signals
        )
        return (HIGHLIGHTS_FIRST_PAGE_TYPE if first else HIGHLIGHTS_PAGE_TYPE), status, []
    return section, status, []


def apply_preparation_page_types(
    parsed: ParsedPdf,
    metadata: Mapping[str, Any],
    overrides: Mapping[str, Mapping[str, str | None]],
) -> None:
    """Detect section types, then apply the manual page types chosen in preparation."""
    classify_preparation_sections(parsed, metadata)
    for page in parsed.pages:
        manual_type = (overrides.get(str(page.page)) or {}).get("page_type")
        if manual_type is not None:
            page.page_type = manual_type


def classify_preparation_sections(
    parsed: ParsedPdf,
    metadata: Mapping[str, Any],
) -> dict[int, dict[str, Any]]:
    """Set `page_type` from the 11 checks and describe how each page was resolved."""
    signals = {
        page.page: detect_section_signals(page, metadata) for page in parsed.pages
    }
    legacy = {page.page: page.page_type for page in parsed.pages}
    resolved = {
        number: _resolve(signals[number], legacy[number]) for number in signals
    }
    notes: dict[int, list[str]] = {number: [] for number in signals}

    highlight_pages = [
        number for number, (page_type, _s, _c) in resolved.items() if page_type in _HIGHLIGHTS_TYPES
    ]
    if highlight_pages:
        last = max(highlight_pages)
        expected = last + 1 if (last + 1) % 2 == 1 else last + 2
        if expected in signals and not signals[expected] and legacy[expected] is None:
            signals[expected].append(
                SectionSignal(
                    TP1_PAGE_TYPE,
                    POSITION,
                    f"first odd page after Highlights page {last}",
                )
            )
            resolved[expected] = _resolve(signals[expected], None)
        for number, (page_type, _status, candidates) in list(resolved.items()):
            if page_type == TP1_PAGE_TYPE and number != expected:
                notes[number].append(f"Highlights/TP1 sequence expects TP1 on page {expected}")
                resolved[number] = (page_type, "partial", candidates)

    analysis: dict[int, dict[str, Any]] = {}
    for page in parsed.pages:
        page_type, status, candidates = resolved[page.page]
        page.page_type = page_type
        analysis[page.page] = {
            "classification_status": status,
            "classification_signals": [signal.as_dict() for signal in signals[page.page]],
            "classification_candidates": candidates,
            "classification_notes": notes[page.page],
        }
    return analysis
