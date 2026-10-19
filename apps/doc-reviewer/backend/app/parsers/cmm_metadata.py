"""Conservative metadata suggestions from the first four pages of a CMM PDF."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypedDict

import fitz

from .cmm_part_numbers import extract_part_numbers

MAX_METADATA_PAGES = 4


class CmmMetadataSuggestions(TypedDict):
    pages_scanned: int
    meta_cmm_number: str | None
    meta_pnr_number: list[str]
    meta_revision_number: str | None
    meta_revision_date: str | None
    meta_first_issue_date: str | None


_HIGHLIGHTS_RE = re.compile(r"(?i)\bHIGHLIGHTS\b")
_CMM_LABEL_RE = re.compile(r"(?i)\b(?:ATA\s+No\.?|CMM\s+(?:No\.?|Number))")
_REVISION_NUMBER_LABEL_RE = re.compile(
    r"(?i)\b(?:revision|rev\.?)(?:\s*(?:no\.?|number))?[.:#-]*\s*(?=\d|$)"
)
_REVISION_DATE_LABEL_RE = re.compile(
    r"(?i)\b(?:revision|rev\.?)\s+date\b"
    r"|\b(?:revision|rev\.?)\s+(?:no\.?|number)\s*\d{1,3}\s+dated\b"
)
_FIRST_ISSUE_LABEL_RE = re.compile(r"(?i)\bfirst\s+issue\b")
_TP1_RE = re.compile(r"(?i)\bTP\s*1\b")
_FIELD_BOUNDARY_RE = re.compile(
    r"(?i)\b(?:"
    r"ATA\s+No\.?|CMM\s+(?:No\.?|Number)|"
    r"revision(?:\s+(?:no\.?|number|date))?|rev\.?\s*(?:no\.?|date)|"
    r"first\s+issue|part\s+number(?:s|\s*\(s\))?"
    r")"
)
_CMM_NUMBER_RE = re.compile(r"(?<![A-Z0-9])\d{2}-\d{2}-\d{2}[A-Z]?(?![A-Z0-9])", re.I)
_REVISION_NUMBER_RE = re.compile(r"(?<![A-Z0-9])\d{1,3}(?![A-Z0-9])", re.I)
_DATE_RE = re.compile(
    r"(?i)(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\.?"
    r"\s+(?:(?:\d{1,2}\s*/\s*)?)(?:\d{2}|\d{4})\b"
)


def suggest_cmm_metadata_from_pdf(path: str | Path) -> CmmMetadataSuggestions:
    pdf = fitz.open(str(path))
    try:
        page_texts = [
            pdf.load_page(index).get_text("text") or ""
            for index in range(min(pdf.page_count, MAX_METADATA_PAGES))
        ]
    finally:
        pdf.close()
    return suggest_cmm_metadata_from_pages(page_texts)


def suggest_cmm_metadata_from_pages(
    page_texts: Sequence[str],
) -> CmmMetadataSuggestions:
    pages = [text or "" for text in page_texts[:MAX_METADATA_PAGES]]
    first_page_lines = _nonempty_lines(pages[0]) if pages else []
    highlights_text = "\n".join(first_page_lines)
    is_highlights_page = bool(_HIGHLIGHTS_RE.search(highlights_text))

    cmm_number = None
    revision_number = None
    revision_date = None
    if is_highlights_page:
        cmm_number = _unique_value(
            _labeled_values(first_page_lines, _CMM_LABEL_RE, _CMM_NUMBER_RE),
            str.upper,
        )
        revision_number = _unique_revision_number(first_page_lines)
        revision_date = _unique_value(
            _labeled_values(
                first_page_lines, _REVISION_DATE_LABEL_RE, _DATE_RE
            ),
            _normalize_date,
        )

    tp1_pages = [
        _nonempty_lines(text)
        for text in pages
        if _is_tp1_page(text) and not _HIGHLIGHTS_RE.search(text)
    ]
    part_numbers = extract_part_numbers(tp1_pages)
    if not part_numbers:
        highlights_pages = [
            _nonempty_lines(text)
            for text in pages
            if _HIGHLIGHTS_RE.search(text)
        ]
        part_numbers = extract_part_numbers(highlights_pages)
    first_issue_date = _unique_value(
        [
            value
            for lines in tp1_pages
            for value in _labeled_values(lines, _FIRST_ISSUE_LABEL_RE, _DATE_RE)
        ],
        _normalize_date,
    )

    return {
        "pages_scanned": len(pages),
        "meta_cmm_number": cmm_number,
        "meta_pnr_number": part_numbers,
        "meta_revision_number": revision_number,
        "meta_revision_date": revision_date,
        "meta_first_issue_date": first_issue_date,
    }


def _nonempty_lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _is_tp1_page(text: str) -> bool:
    return bool(
        _TP1_RE.search(text)
        or (
            _REVISION_NUMBER_LABEL_RE.search(text)
            and _FIRST_ISSUE_LABEL_RE.search(text)
        )
    )


def _labeled_values(
    lines: list[str],
    label_pattern: re.Pattern[str],
    value_pattern: re.Pattern[str],
) -> list[str]:
    values: list[str] = []
    for line_index, line in enumerate(lines):
        labels = list(label_pattern.finditer(line))
        for label_index, label in enumerate(labels):
            tail_end = labels[label_index + 1].start() if label_index + 1 < len(labels) else len(line)
            tail = line[label.end():tail_end]
            boundary = _FIELD_BOUNDARY_RE.search(tail)
            if boundary is not None:
                tail = tail[:boundary.start()]
            value = _leading_value(tail, value_pattern)
            if value is None and not re.search(r"[A-Z0-9]", tail, re.I):
                next_line = _next_nonempty_line(lines, line_index + 1)
                if next_line is not None and not _FIELD_BOUNDARY_RE.search(next_line):
                    value = _leading_value(next_line, value_pattern)
            if value:
                values.append(value)
    return values


def _leading_value(text: str, value_pattern: re.Pattern[str]) -> str | None:
    normalized = text.strip().lstrip(
        " :;#-\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
    ).strip()
    match = value_pattern.match(normalized)
    return match.group(0) if match is not None else None


def _next_nonempty_line(lines: list[str], start: int) -> str | None:
    return next((line for line in lines[start:] if line), None)


def _unique_revision_number(lines: list[str]) -> str | None:
    values = _labeled_values(
        lines, _REVISION_NUMBER_LABEL_RE, _REVISION_NUMBER_RE
    )
    return _unique_value(values, str)


def _unique_value(
    values: list[str],
    normalize: Callable[[str], str],
) -> str | None:
    unique: dict[str, str] = {}
    for value in values:
        normalized = normalize(value)
        if normalized:
            unique.setdefault(normalized.casefold(), normalized)
    return next(iter(unique.values())) if len(unique) == 1 else None


def _normalize_date(value: str) -> str:
    normalized = re.sub(r"\s*/\s*", "/", value.strip()).upper()
    return re.sub(r"\s+", " ", normalized).replace(".", "")
