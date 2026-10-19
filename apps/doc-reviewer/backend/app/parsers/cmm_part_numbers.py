"""Extract labeled Part Number and PNR values from CMM pages."""

from __future__ import annotations

import re
from collections.abc import Sequence

_PART_NUMBER_LABEL_RE = re.compile(r"(?i)\b(?:part\s+number(?:s|\s*\(s\))?|PNR)\b")
_FIELD_BOUNDARY_RE = re.compile(
    r"(?i)\b(?:"
    r"ATA\s+No\.?|CMM\s+(?:No\.?|Number)|"
    r"revision(?:\s+(?:no\.?|number|date))?|rev\.?\s*(?:no\.?|date)|"
    r"first\s+issue|part\s+number(?:s|\s*\(s\))?|PNR"
    r")"
)
_PART_NUMBER_TOKEN_RE = re.compile(
    r"(?i)(?<![A-Z0-9])"
    r"(?=[A-Z0-9._:/\-\u2010-\u2015\u2212]*\d)"
    r"[A-Z0-9][A-Z0-9._:/\-\u2010-\u2015\u2212]{2,}[A-Z0-9]"
    r"(?![A-Z0-9])"
)


def extract_part_numbers(tp1_pages: Sequence[Sequence[str]]) -> list[str]:
    values: list[str] = []
    for lines in tp1_pages:
        for line_index, line in enumerate(lines):
            labels = list(_PART_NUMBER_LABEL_RE.finditer(line))
            for label_index, label in enumerate(labels):
                tail_end = (
                    labels[label_index + 1].start()
                    if label_index + 1 < len(labels)
                    else len(line)
                )
                tail = line[label.end():tail_end]
                boundary = _FIELD_BOUNDARY_RE.search(tail)
                if boundary is not None:
                    tail = tail[:boundary.start()]
                values.extend(_part_number_values(tail))

                for next_line in lines[line_index + 1:]:
                    if _FIELD_BOUNDARY_RE.search(next_line):
                        break
                    next_values = _part_number_values(next_line)
                    if next_values:
                        values.extend(next_values)
                        continue
                    break

    unique: dict[str, str] = {}
    for value in values:
        unique.setdefault(value.casefold(), value)
    return list(unique.values()) if len(unique) <= 50 else []


def _part_number_values(text: str) -> list[str]:
    matches = list(_PART_NUMBER_TOKEN_RE.finditer(text))
    if not matches:
        return []
    cursor = 0
    values: list[str] = []
    for match in matches:
        if not _is_part_number_separator(text[cursor:match.start()]):
            return []
        value = re.sub(
            r"\s*([\- \u2010-\u2015\u2212_/. :])\s*",
            r"\1",
            match.group(0),
        ).strip()
        if len(value) < 4 or not any(character.isdigit() for character in value):
            return []
        values.append(value)
        cursor = match.end()
    if not _is_part_number_separator(text[cursor:]):
        return []
    return values


def _is_part_number_separator(value: str) -> bool:
    without_and = re.sub(r"(?i)\band\b", "", value)
    return not re.search(r"[A-Z0-9]", without_and, re.I)
