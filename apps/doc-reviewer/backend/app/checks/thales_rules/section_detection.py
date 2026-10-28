"""THALES preparation: section detection from the 11 documented checks.

Each page is read for independent signal families (footer label / number range,
title line, table or content cues, position in the Highlights -> TP1 sequence).
Two families agreeing confirm a section; one family only leaves it partial;
signals pointing at different sections are a conflict and stay unclassified.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
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
_TITLE_PAGE_TYPES = {
    "TESTING": TESTING,
    "TESTING AND FAULT ISOLATION": TESTING,
    "TESTS": TESTING,
    "REPAIR": REPAIR,
    "ASSEMBLY": ASSEMBLY,
    "ASSEMBLY AND STORAGE": ASSEMBLY,
    "ASSEMBLY INCLUDING STORAGE": ASSEMBLY,
    "ASSEMBLY (INCLUDING STORAGE)": ASSEMBLY,
    "VENDOR CODE LIST": VENDOR_CODE_LIST,
    "TABLE OF CONTENTS": TABLE_OF_CONTENTS,
    "INTRODUCTION": INTRODUCTION,
    "RECORD OF REVISIONS": ROR,
    "LIST OF EFFECTIVE PAGES": LEP,
    "CONSUMABLES": SPECIAL_TOOLS,
    "LIST OF CONSUMABLES": SPECIAL_TOOLS,
    "LIST OF MATERIALS": SPECIAL_TOOLS,
    "MATERIALS": SPECIAL_TOOLS,
    "SPECIAL EQUIPMENT AND TOOLING": SPECIAL_TOOLS,
}
DEFAULT_PREPARATION_TITLES = tuple(
    dict.fromkeys(
        [
            *_TITLE_PAGE_TYPES,
            "RECORD OF TEMPORARY REVISIONS",
            "RECORD OF SERVICE BULLETINS",
            "LIST OF APPROVED REPAIRERS",
            "DISASSEMBLY",
            "CLEANING",
            "REASSEMBLY",
            "TROUBLE SHOOTING",
            "STORAGE INSTRUCTIONS",
            "ILLUSTRATED PARTS LIST",
            "DETAILED PARTS LIST",
        ]
    )
)
_FOOTER_LABELS = (
    (HIGHLIGHTS_PAGE_TYPE, re.compile(r"(?i)\bHigh?lights?\s+Page\s+(\d+)")),
    (TP1_PAGE_TYPE, re.compile(r"(?i)\bTP(?:\s+Page\s+|\s*-\s*|\s+)(\d+)")),
    (ROR, re.compile(r"(?i)\b(?:ROR\s+Page\s+|RR\s*-\s*)(\d+)")),
    (LEP, re.compile(r"(?i)\b(?:LEP\s+Page\s+|LEP\s*-\s*)(\d+)")),
    (INTRODUCTION, re.compile(r"(?i)\b(?:INTRO\s+Page\s+|INTRO\s*-\s*)(\d+)")),
    (TABLE_OF_CONTENTS, re.compile(r"(?i)\b(?:TC\s+Page\s+|TC\s*-\s*)(\d+)")),
    (SPECIAL_TOOLS, re.compile(r"(?i)\b(?:LM\s+Page\s+|LM\s*-\s*)(\d+)")),
)
_NUMBERED_PREFIX_RE = re.compile(r"^\d+(?:\.\d+)*[.)]?\s+")
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


def _normalize_title(value: str) -> str:
    without_number = _NUMBERED_PREFIX_RE.sub("", value.strip())
    return " ".join(without_number.split()).upper()


def page_type_for_title(title: str) -> str:
    normalized = _normalize_title(title)
    return _TITLE_PAGE_TYPES.get(normalized, normalized)


def page_types_for_titles(titles: Iterable[str]) -> dict[str, str]:
    return {
        _normalize_title(title): page_type_for_title(title)
        for title in titles
    }


def _unlisted_title_candidate(page: ParsedPage) -> str | None:
    def valid_title(text: str) -> str | None:
        normalized = " ".join(text.split())
        words = normalized.split()
        if (
            not normalized
            or len(normalized) > 60
            or not 2 <= len(words) <= 8
            or not any(character.isalpha() for character in normalized)
            or re.search(r"[.!?]", normalized)
        ):
            return None
        return normalized

    if page.lines and page.page_height > 0 and page.page_width > 0:
        body_sizes = sorted(
            span.size
            for span in page.spans
            if span.size > 0 and span.bbox[1] < page.page_height * 0.8
        )
        median_size = body_sizes[len(body_sizes) // 2] if body_sizes else 0
        candidates: list[str] = []
        for line in page.lines:
            title = valid_title(line.text)
            x0, y0, x1, y1 = line.bbox
            centered = abs((x0 + x1) / 2 - page.page_width / 2) <= page.page_width * 0.28
            left_aligned = x0 <= page.page_width * 0.22
            if (
                title is None
                or not page.page_height * 0.03 <= y0 <= page.page_height * 0.42
                or not (left_aligned or centered)
            ):
                continue
            matching_spans = [
                span
                for span in page.spans
                if span.bbox[1] < y1 and span.bbox[3] > y0
            ]
            if title.isupper() or any(
                span.size >= max(12, median_size * 1.2)
                or "bold" in span.font.casefold()
                for span in matching_spans
            ):
                candidates.append(title)
    else:
        candidates = [
            title
            for line in _text_lines(page)[:4]
            if (title := valid_title(line)) is not None
            and title.isupper()
        ]
    unique = list(dict.fromkeys(candidates))
    return unique[0] if len(unique) == 1 else None


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


def _title_signals(page: ParsedPage, page_titles: Mapping[str, str]) -> list[SectionSignal]:
    signals: list[SectionSignal] = []
    for line in _text_lines(page):
        section = page_titles.get(_normalize_title(line))
        if section is not None:
            signals.append(SectionSignal(section, TITLE, f"title: {line}"))
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


def detect_section_signals(
    page: ParsedPage,
    metadata: Mapping[str, Any],
    page_titles: Mapping[str, str] | None = None,
) -> list[SectionSignal]:
    title_types = (
        page_titles
        if page_titles is not None
        else {
            _normalize_title(title): page_type_for_title(title)
            for title in DEFAULT_PREPARATION_TITLES
        }
    )
    signals = _footer_signals(page) + _title_signals(page, title_types) + _content_signals(page, metadata)
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
    page_titles: Mapping[str, str] | None = None,
) -> None:
    """Detect section types, then apply the manual page types chosen in preparation."""
    classify_preparation_sections(parsed, metadata, page_titles)
    for page in parsed.pages:
        manual_type = (overrides.get(str(page.page)) or {}).get("page_type")
        if manual_type is not None:
            page.page_type = manual_type


def classify_preparation_sections(
    parsed: ParsedPdf,
    metadata: Mapping[str, Any],
    page_titles: Mapping[str, str] | None = None,
) -> dict[int, dict[str, Any]]:
    """Classify configured title pages and carry their type across continuation pages."""
    signals = {
        page.page: detect_section_signals(page, metadata, page_titles)
        for page in parsed.pages
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

    active_section: str | None = None
    section_page = 0
    for page in parsed.pages:
        page_type, status, _candidates = resolved[page.page]
        if status == "conflict":
            active_section = None
            section_page = 0
        elif any(signal.family == TITLE for signal in signals[page.page]):
            active_section = page_type
            section_page = 1
        elif page_type is None and not signals[page.page] and legacy[page.page] is None:
            unlisted_title = _unlisted_title_candidate(page)
            if unlisted_title is not None:
                notes[page.page].append(f"Title not in the configured list: {unlisted_title}")
                active_section = None
                section_page = 0
            elif active_section is not None:
                section_page += 1
                signals[page.page].append(
                    SectionSignal(
                        active_section,
                        POSITION,
                        f"continuation: {active_section} page {section_page}",
                    )
                )
                resolved[page.page] = (active_section, "partial", [])
        elif page_type == active_section and active_section is not None:
            section_page += 1
        else:
            active_section = None
            section_page = 0

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
