"""Scoring des pages PDF selon les titres DMRL et les indices de section."""

from __future__ import annotations

import json
import re

from app.core.dmrl import entry_from_dict, normalize
from app.core.dmrl_rules import data_module_entries

_TOC_LINE = re.compile(r"(?:\.{2,}|·{2,}|-{2,})\s*\d+\s*$")
_CHAPTER = re.compile(r"^(?:chapter|chapitre)\s+1(?:\b|\s*[-:.])", re.IGNORECASE)
_NUMBERED_SECTION = re.compile(r"^\d+\.\d+\b")


def dmrl_data_module_titles(dmrl_json: str | None) -> list[str]:
    if not dmrl_json:
        return []
    try:
        raw_entries = json.loads(dmrl_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(raw_entries, list):
        return []

    entries = [
        entry_from_dict(entry)
        for entry in raw_entries
        if isinstance(entry, dict)
    ]
    return list(dict.fromkeys(
        entry.title.strip()
        for entry in data_module_entries(entries)
        if entry.title.strip()
    ))


def dmrl_scoring_title(dmrl_json: str | None) -> str:
    return next(iter(dmrl_data_module_titles(dmrl_json)), "")


def score_page(text: str, title: str) -> tuple[float, list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized_title = normalize(title)
    normalized_lines = [normalize(line) for line in lines]
    title_match = bool(normalized_title) and any(
        normalized_title in line for line in normalized_lines
    )

    reasons: list[str] = []
    score = 0.0

    if normalized_title:
        if normalized_title in normalized_lines:
            score += 100
            reasons.append("dmrl_title_exact")
        elif any(line.startswith(normalized_title) for line in normalized_lines):
            score += 70
            reasons.append("dmrl_title_prefix")
        elif title_match:
            score += (45 + 80) if any(
                _NUMBERED_SECTION.search(line)
                and not _TOC_LINE.search(line)
                and normalized_title in normalized
                for line, normalized in zip(lines, normalized_lines, strict=True)
            ) else 45
            reasons.append("dmrl_title_contains")

    if any(_CHAPTER.search(line) for line in lines):
        score += 45
        reasons.append("chapter_1")

    if any(_NUMBERED_SECTION.search(line) and not _TOC_LINE.search(line) for line in lines):
        score += 45
        reasons.append("numbered_section")

    text_chars = len(" ".join(lines))
    score += min(text_chars / 80.0, 20.0)
    if text_chars >= 180:
        score += 10
        reasons.append("text_density")
    elif text_chars < 40:
        score -= 20
        reasons.append("low_text_density")

    toc_lines = sum(bool(_TOC_LINE.search(line)) for line in lines)
    if toc_lines >= 2:
        score -= min(45.0, 15.0 * toc_lines)
        reasons.append("toc_like_lines")
    if any(
        normalize(line) in {"sommaire", "table des matieres", "contents", "table of contents"}
        for line in lines[:5]
    ):
        score -= 30
        reasons.append("toc_heading")

    return round(score, 2), reasons
