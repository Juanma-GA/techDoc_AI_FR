"""Wrap `core.units_detector` so its matches integrate with the rules engine."""

from __future__ import annotations

from typing import Literal

from app.checks.raw import RawSuggestion
from app.core.units_detector import detect
from app.parsers.pdf_parser import ParsedPage

UnitSystem = Literal["metric", "imperial", "auto"]


def run(pages: list[ParsedPage], target_system: UnitSystem) -> list[RawSuggestion]:
    suggestions: list[RawSuggestion] = []
    for page in pages:
        for match in detect(page.text, target_system):
            suggestions.append(
                RawSuggestion(
                    rule_kind="units",
                    rule_code="UNITS_CONVERT",
                    severity="info",
                    message=f"Conversion proposée vers le système {match.target_system}.",
                    original=match.original,
                    proposed=match.proposed,
                    page=page.page,
                    span=match.span,
                )
            )
    return suggestions
