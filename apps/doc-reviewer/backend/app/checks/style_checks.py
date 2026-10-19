"""Sentence-length checks for standard catalogs.

Word counts and the STE procedural/descriptive thresholds are handled here,
then routed by `catalog_runner`. The `proposed` text remains unchanged; the
qualitative rewrite is delegated to `rules_engine._enrich_with_ai`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from app.checks.raw import RawSuggestion
from app.parsers.pdf_parser import ParsedPage

_RE_SENTENCE_END = re.compile(r"[.!?]+[\"'\u2019”)\]]*(?=\s|$)")
_RE_ABBREVIATION_END = re.compile(
    r"(?i)(?:\b(?:e\.g|i\.e|etc|fig|no|rev|dr|mr|mrs|ms|vs|approx|sec|ch)\.|"
    r"(?:\b[A-Z]\.){1,3})[\"'\u2019”)\]]*$"
)
_RE_STEP_PREFIX = re.compile(
    r"(?i)^\s*(?:(?:step\s+)?\d+(?:\.\d+)*[.):]|[a-z][.)]|[-*•▪])\s+"
)
_RE_STEP_LABEL = re.compile(
    r"(?i)^\s*(?:(?:step\s+)?\d+(?:\.\d+)*[.):]|[a-z][.)])\s*$"
)
_DEFAULT_PROCEDURAL_MAX_WORDS = 20
_DEFAULT_DESCRIPTIVE_MAX_WORDS = 25
_PREVIEW_MAX = 200


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _sentence_spans(text: str) -> Iterator[tuple[int, int]]:
    cursor = 0
    for match in _RE_SENTENCE_END.finditer(text):
        candidate = text[cursor : match.end()].strip()
        if not candidate:
            cursor = match.end()
            continue
        if _RE_STEP_LABEL.fullmatch(candidate) or _RE_ABBREVIATION_END.search(candidate):
            continue
        start = cursor + len(text[cursor : match.end()]) - len(text[cursor : match.end()].lstrip())
        end = cursor + len(text[cursor : match.end()].rstrip())
        yield start, end
        cursor = match.end()

    tail = text[cursor:]
    if tail.strip():
        start = cursor + len(tail) - len(tail.lstrip())
        end = cursor + len(tail.rstrip())
        yield start, end


def _check_page(page: ParsedPage, rule: dict, max_words: int) -> Iterable[RawSuggestion]:
    text = page.text or ""
    code = rule.get("code") or "STE_LONG_SENTENCE"
    severity = rule.get("severity") or "warning"
    descriptive_max_words = _positive_int(
        rule.get("descriptive_max_words"),
        _DEFAULT_DESCRIPTIVE_MAX_WORDS,
    )
    for start, end in _sentence_spans(text):
        sentence = text[start:end]
        countable_sentence = _RE_STEP_PREFIX.sub("", sentence, count=1)
        word_count = len(countable_sentence.split())
        limit = max_words if _RE_STEP_PREFIX.match(sentence) else descriptive_max_words
        if word_count <= limit:
            continue
        preview = sentence
        if len(preview) > _PREVIEW_MAX:
            preview = preview[:_PREVIEW_MAX] + "…"
        yield RawSuggestion(
            rule_kind="standard",
            rule_code=code,
            severity=severity,
            message=(
                rule.get("message")
                or f"Phrase de {word_count} mots — STE100 limite à {limit}."
            ),
            original=preview,
            proposed=preview,
            page=page.page,
            span=(start, min(end, start + len(preview))),
        )


def run(pages: list[ParsedPage], rule: dict) -> list[RawSuggestion]:
    """Applique la règle `sentence_length` `rule` à chaque page."""
    max_words = _positive_int(
        rule.get("pattern"),
        _DEFAULT_PROCEDURAL_MAX_WORDS,
    )
    out: list[RawSuggestion] = []
    for page in pages:
        out.extend(_check_page(page, rule, max_words))
    return out
