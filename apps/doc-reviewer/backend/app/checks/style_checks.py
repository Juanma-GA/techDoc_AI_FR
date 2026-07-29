"""Contrôles de style non exprimables en regex.

La longueur de phrase (nombre de mots) ne peut pas être détectée par une
expression régulière — d'où le pattern sentinelle historique
`STE100_LONG_SENTENCE` qui, compilé comme regex, ne matchait jamais rien : la
règle STE_LONG_SENTENCE était donc silencieusement inopérante. Ce module
rétablit un vrai détecteur, câblé au catalogue via le kind `sentence_length`
(cf. `catalog_runner`). Le `proposed` reste égal à l'`original` : la réécriture
qualitative est confiée à Mistral par `rules_engine._enrich_with_ai`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.checks.raw import RawSuggestion
from app.parsers.pdf_parser import ParsedPage

_RE_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ÿ])")
_DEFAULT_MAX_WORDS = 20  # ASD-STE100 §6.4 : ~20 mots par phrase procédurale.
_PREVIEW_MAX = 200


def _parse_threshold(rule: dict) -> int:
    """Le seuil de mots est porté par le champ `pattern` du catalogue
    (chaîne numérique). Repli sur le défaut STE100 si absent/illisible."""
    raw = str(rule.get("pattern") or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_WORDS
    return value if value > 0 else _DEFAULT_MAX_WORDS


def _check_page(page: ParsedPage, rule: dict, max_words: int) -> Iterable[RawSuggestion]:
    text = page.text or ""
    cursor = 0
    code = rule.get("code") or "STE_LONG_SENTENCE"
    severity = rule.get("severity") or "warning"
    for sentence in _RE_SENTENCE_SPLIT.split(text):
        start = text.find(sentence, cursor)
        if start < 0:
            cursor += len(sentence)
            continue
        cursor = start + len(sentence)
        words = sentence.split()
        if len(words) <= max_words:
            continue
        preview = sentence.strip()
        if len(preview) > _PREVIEW_MAX:
            preview = preview[:_PREVIEW_MAX] + "…"
        yield RawSuggestion(
            rule_kind="standard",
            rule_code=code,
            severity=severity,
            message=(
                rule.get("message")
                or f"Phrase de {len(words)} mots — STE100 limite à {max_words}."
            ),
            original=preview,
            proposed=preview,
            page=page.page,
            span=(start, start + len(preview)),
        )


def run(pages: list[ParsedPage], rule: dict) -> list[RawSuggestion]:
    """Applique la règle `sentence_length` `rule` à chaque page."""
    max_words = _parse_threshold(rule)
    out: list[RawSuggestion] = []
    for page in pages:
        out.extend(_check_page(page, rule, max_words))
    return out
