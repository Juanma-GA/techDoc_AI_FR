"""Heuristics for note and callout blocks in legacy documents."""

from __future__ import annotations

import re

_NOTE_RE = re.compile(
    r"^\s*(?:n\.?\s*b\.?|note|nota|remarque|a\s+noter|important|important\s+note)\s*[:.-]?\s*",
    re.IGNORECASE,
)
_BACKGROUND_RE = re.compile(
    r"^\s*(?:background|contexte|pour\s+information|information\s+generale|a\s+savoir)\s*[:.-]?\s*",
    re.IGNORECASE,
)


def detect_note_kind(text: str) -> str | None:
    """Return the normalized admonition kind for a note or contextual callout."""
    if _NOTE_RE.match(text or ""):
        return "note"
    if _BACKGROUND_RE.match(text or ""):
        return "note"
    return None
