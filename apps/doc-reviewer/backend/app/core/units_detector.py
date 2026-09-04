"""Detect unit literals in raw text and propose conversions.

Supported : mm / cm / m vs in / inch / ft / ' / "  +  kg vs lb.

The detector is text-only — bbox resolution is the responsibility of
`checks/units_check.py`, which crosses the (start, end) span with
PyMuPDF's `page.get_text("dict")` blocks/lines/spans.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

UnitSystem = Literal["metric", "imperial", "auto"]


@dataclass(frozen=True)
class UnitMatch:
    span: tuple[int, int]
    original: str
    proposed: str
    value: float
    unit: str
    target_system: Literal["metric", "imperial"]


_PATTERNS: list[tuple[str, str, str]] = [
    # (unit_id, system, regex)
    (
        "mm",
        "metric",
        r"(?P<v>\d+(?:[.,]\d+)?)\s*(?:mm|millim[eè]tres?)\b",
    ),
    (
        "cm",
        "metric",
        r"(?P<v>\d+(?:[.,]\d+)?)\s*(?:cm|centim[eè]tres?)\b",
    ),
    (
        "m",
        "metric",
        r"(?P<v>\d+(?:[.,]\d+)?)\s*(?:m|m[eè]tres?)\b(?!\w)",
    ),
    (
        "kg",
        "metric",
        r"(?P<v>\d+(?:[.,]\d+)?)\s*(?:kg|kilos?|kilogrammes?)\b",
    ),
    (
        "in",
        "imperial",
        r"(?P<v>\d+(?:[.,]\d+)?)\s*(?:inches|inch|in\b|\")",
    ),
    (
        "ft",
        "imperial",
        r"(?P<v>\d+(?:[.,]\d+)?)\s*(?:feet|foot|ft\b|')",
    ),
    (
        "lb",
        "imperial",
        r"(?P<v>\d+(?:[.,]\d+)?)\s*(?:lbs|lb|pounds?)\b",
    ),
]

_COMPILED: list[tuple[str, str, re.Pattern[str]]] = [
    (uid, sys, re.compile(p, re.IGNORECASE)) for (uid, sys, p) in _PATTERNS
]


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "."))


def _format(value: float, unit: str) -> str:
    rounded = round(value, 2)
    if rounded == int(rounded):
        return f"{int(rounded)} {unit}"
    return f"{rounded:.2f} {unit}"


def _convert(value: float, unit: str, target: Literal["metric", "imperial"]) -> tuple[float, str]:
    table = {
        ("mm", "imperial"): (value / 25.4, "in"),
        ("cm", "imperial"): (value / 2.54, "in"),
        ("m", "imperial"): (value * 3.281, "ft"),
        ("kg", "imperial"): (value * 2.2046, "lb"),
        ("in", "metric"): (value * 2.54, "cm"),
        ("ft", "metric"): (value * 0.3048, "m"),
        ("lb", "metric"): (value * 0.4536, "kg"),
    }
    converted_value, new_unit = table[(unit, target)]
    return converted_value, new_unit


def _majority_system(text: str) -> Literal["metric", "imperial"]:
    metric = imperial = 0
    for _uid, system, pattern in _COMPILED:
        for _ in pattern.finditer(text):
            if system == "metric":
                metric += 1
            else:
                imperial += 1
    return "metric" if metric >= imperial else "imperial"


def detect(text: str, target_system: UnitSystem) -> list[UnitMatch]:
    if target_system == "auto":
        majority: Literal["metric", "imperial"] = _majority_system(text)
        # Convert the *minority* system into the majority.
        target: Literal["metric", "imperial"] = majority
    else:
        target = target_system

    matches: list[UnitMatch] = []
    for unit_id, origin_system, pattern in _COMPILED:
        if origin_system == target:
            continue
        for m in pattern.finditer(text):
            try:
                value = _to_float(m.group("v"))
            except (ValueError, KeyError):
                continue
            converted_value, new_unit = _convert(value, unit_id, target)
            matches.append(
                UnitMatch(
                    span=(m.start(), m.end()),
                    original=m.group(0),
                    proposed=_format(converted_value, new_unit),
                    value=value,
                    unit=unit_id,
                    target_system=target,
                )
            )
    return matches
