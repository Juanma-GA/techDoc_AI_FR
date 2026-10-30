"""Recognise an S1000D publication so its rules (and not the ATA100 ones) apply to it."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from app.parsers.pdf_parser import ParsedPdf

from .data_modules import DMC_RE, complete_pages, is_s1000d_document, parse_issue_date

_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_ISSUE_BLOCK_RE = re.compile(
    r"(?im)^[ \t]*Issue[ \t]+No\.?[ \t]*:?[ \t]*(?P<number>\d{1,3})[ \t]*\n[ \t]*(?P<date>[^\n]{4,30})$"
)
_SNS_RE = re.compile(r"(?m)^\s*(\d{2}-\d{2}-\d{2}[A-Z]?)\s*$")
_PRODUCT_CONFIGURATION_RE = re.compile(r"(?i)product\s+configuration")
_PUBLICATION_CONFIGURATION_RE = re.compile(r"(?i)publication\s+configuration")
_PART_NUMBER_RE = re.compile(r"[A-Z0-9][A-Z0-9./-]{4,}")
_HIGHLIGHTS_TITLE_RE = re.compile(r"(?m)^\s*HIGHLIGHTS\s*$")


def matches_document(parsed: Any) -> bool:
    """True when the PDF prints a LIST OF EFFECTIVE DATA MODULES listing data module codes."""
    return isinstance(parsed, ParsedPdf) and is_s1000d_document(complete_pages(parsed))


def _revision_date(text: str) -> str | None:
    found = parse_issue_date(text)
    if found is None:
        return None
    month = _MONTHS[found.month - 1]
    return f"{month} {found.day:02d}/{found.year % 100:02d}" if found.day else f"{month} {found.year}"


def _prime_part_numbers(pages: Sequence[str]) -> list[str]:
    """PRIME rows of the product configuration table: the OEM top-level part numbers."""
    for text in pages:
        start = _PRODUCT_CONFIGURATION_RE.search(text)
        if start is None:
            continue
        end = _PUBLICATION_CONFIGURATION_RE.search(text, start.end())
        section = text[start.end() : end.start() if end else len(text)]
        lines = [line.strip() for line in section.splitlines() if line.strip()]
        numbers = [
            following
            for current, following in zip(lines, lines[1:])
            if current.upper() == "PRIME" and _PART_NUMBER_RE.fullmatch(following)
        ]
        return list(dict.fromkeys(numbers))
    return []


def _update_type(pages: Sequence[str]) -> str | None:
    """Migration when every reason for update of the HIGHLIGHTS says so, MCO when one does not."""
    reasons: list[str] = []
    for text in pages:
        if not _HIGHLIGHTS_TITLE_RE.search(text):
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        reasons.extend(
            following for current, following in zip(lines, lines[1:]) if DMC_RE.fullmatch(current)
        )
    if not reasons:
        return None
    return "Migration" if all("migration" in reason.casefold() for reason in reasons) else "MCO"


def suggest_metadata(pages: Sequence[str]) -> dict[str, Any]:
    """Mapping values readable in the front matter; S1000D does not print the first issue date."""
    cover = pages[0] if pages else ""
    issue = _ISSUE_BLOCK_RE.search(cover)
    sns = sorted({match.group(1) for match in _SNS_RE.finditer(cover)})
    return {
        "meta_cmm_number": sns[0] if len(sns) == 1 else None,
        "meta_pnr_number": _prime_part_numbers(pages),
        "meta_revision_number": issue.group("number") if issue is not None else None,
        "meta_revision_date": _revision_date(issue.group("date")) if issue is not None else None,
        "meta_first_issue_date": None,
        "meta_update_type": _update_type(pages),
    }
