"""Built-in S1000D / STE100 rule checks for maintenance manuals.

Each rule is described in `S1000D_BUILTIN_RULES` for UI consumption (the
preview HTML and the React settings page list them with title/description
and a per-code toggle). The runner skips rules whose code is present in
`disabled_codes` (typically loaded from `app_config['s1000d.disabled_codes']`).

Rules focus on **maintenance documents** (procedures, descriptions, BREX),
not on DMC tokens. Regex patterns are intentionally conservative — false
positives are preferable to silent misses; the user always has the final
say via Accept / Edit / Reject.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.parsers.pdf_parser import ParsedPage


@dataclass
class RawSuggestion:
    rule_kind: str
    rule_code: str
    severity: str
    message: str
    original: str
    proposed: str
    page: int
    span: tuple[int, int]
    # Bbox pre-calculee en POINTS PDF (x0, y0, x1, y1). Renseignee par les
    # controles geometriques (layout) qui connaissent deja la position exacte
    # et n'ont pas de texte a localiser via search_for. None = laisser
    # `materialize` calculer la bbox depuis `original`.
    bbox: tuple[float, float, float, float] | None = None


# ---- Rule catalog (UI consumption + runner gating) ----------------------

S1000D_BUILTIN_RULES: list[dict[str, str]] = [
    {
        "code": "STE_LONG_SENTENCE",
        "severity": "warning",
        "title": "Phrase trop longue (STE100)",
        "description": (
            "Le Simplified Technical English (ASD-STE100) recommande au "
            "maximum 25 mots par phrase procédurale et 20 mots par phrase "
            "descriptive. Au-delà, la phrase devient ambiguë et difficile "
            "à traduire."
        ),
        "example_invalid": "When the operator wants to remove the panel he must first ensure the equipment is fully de-energised and then he must use the dedicated tool that is provided in the maintenance kit.",
        "example_valid": "De-energise the equipment. Use the dedicated tool from the maintenance kit to remove the panel.",
    },
    {
        "code": "STE_PASSIVE_VOICE",
        "severity": "info",
        "title": "Voix passive (STE100)",
        "description": (
            "STE100 impose la voix active dans les procédures : « Retirez "
            "la vis » plutôt que « La vis doit être retirée ». La voix "
            "passive masque l'agent et complique la lecture."
        ),
        "example_invalid": "The screw is to be removed by the operator.",
        "example_valid": "Remove the screw.",
    },
    {
        "code": "STE_FIRST_PERSON",
        "severity": "warning",
        "title": "Première personne interdite",
        "description": (
            "Les manuels de maintenance s'adressent à un opérateur dans "
            "un ton neutre et impersonnel. Les pronoms à la première "
            "personne (« I », « we », « our », « nous », « notre ») ne "
            "doivent pas apparaître."
        ),
        "example_invalid": "We recommend that you check the pressure.",
        "example_valid": "Check the pressure.",
    },
    {
        "code": "STE_PROCEDURAL_GERUND",
        "severity": "info",
        "title": "Gérondif en début de procédure",
        "description": (
            "STE100 demande des verbes à l'impératif pour les procédures. "
            "Les gérondifs en début de phrase (« Removing… », « Avant de "
            "retirer… ») ralentissent la lecture et génèrent des "
            "ambiguïtés temporelles."
        ),
        "example_invalid": "Removing the cover, ensure the system is off.",
        "example_valid": "Ensure the system is off. Then remove the cover.",
    },
    {
        "code": "S1000D_WARNING_FORMAT",
        "severity": "warning",
        "title": "Format des avertissements",
        "description": (
            "Les notices WARNING / CAUTION / DANGER doivent apparaître "
            "sur une ligne dédiée, en MAJUSCULES, avant la procédure "
            "concernée. Les warnings inline dans une phrase sont "
            "sous-S1000D 4.x."
        ),
        "example_invalid": "Disconnect the power, warning: high voltage, before opening.",
        "example_valid": "WARNING\nHigh voltage. Disconnect the power before opening.",
    },
    {
        "code": "S1000D_DOUBLE_SPACE",
        "severity": "info",
        "title": "Espaces doubles",
        "description": (
            "Détecte les séquences de 2 espaces ou plus dans le contenu. "
            "Le standard S1000D recommande un seul espace après la "
            "ponctuation pour préserver le rendu typographique."
        ),
        "example_invalid": "Step 1.  Open the panel",
        "example_valid": "Step 1. Open the panel",
    },
]


# ---- Detectors -----------------------------------------------------------

_RE_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ÿ])")
_LONG_SENTENCE_THRESHOLD = 25  # words

# Voix passive : "is/are/was/were/be/been/being + past participle (-ed/-en)".
# Conservateur — on prend les formes courantes anglaises sur les pages
# "procedure". Le franç. utilise "est/sont/a été/ont été + participe" mais
# on évite les faux positifs ici (un POC).
_RE_PASSIVE = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+\w+(?:ed|en)\b",
    re.IGNORECASE,
)

# Première personne FR + EN.
_RE_FIRST_PERSON = re.compile(
    r"\b(?:I|we|my|our|us|nous|notre|nos|je|mon|ma|mes)\b",
    re.IGNORECASE,
)

# Gérondif en début de phrase / paragraphe : "Removing the …", "Avant de
# retirer …". Détection simple : ligne qui commence par <Verb>ing ou par
# "When/Before/After …ing".
_RE_GERUND_START = re.compile(
    r"(?:^|(?<=[.!?]\s))(?:When|Before|After|While)\s+\w+ing\b",
    re.MULTILINE,
)

# Warning inline : "warning:" ou "caution:" en milieu de phrase (pas en
# début de ligne, pas en majuscule isolée).
_RE_WARNING_INLINE = re.compile(
    r"(?<![A-Z\n])\b(?:warning|caution|danger)\s*[:,]",
    re.IGNORECASE,
)


# Regex detection only. The `proposed` field stays equal to `original`
# at this stage — `rules_engine` enriches qualitative rule codes with a
# Mistral rewrite (batch call) before persistence. No hardcoded
# transformations: a Python-level lemmatiser cannot reliably rewrite
# natural-language sentences without producing nonsense words.


def _expand_to_sentence(text: str, span_start: int, span_end: int) -> tuple[int, int, str]:
    """Walk left/right from `[span_start, span_end)` to the surrounding
    sentence boundaries (period / question / exclam / newline). Returns
    `(sentence_start, sentence_end, sentence_text)` — the slice is stripped
    of leading/trailing whitespace.

    Single-mot detection is way too narrow for the LLM and the apply step:
    `is designed → designed` was a no-op, and even auxiliary stripping lost
    the surrounding clause. Pulling the whole sentence preserves context
    so Mistral can rewrite around the matched span."""
    if span_start < 0 or span_end > len(text):
        return span_start, span_end, text[span_start:span_end]

    # Walk backward to the previous sentence terminator.
    s = span_start
    while s > 0 and text[s - 1] not in ".!?\n":
        s -= 1
    # Skip leading whitespace inside the new sentence.
    while s < span_start and text[s] in " \t\r\n":
        s += 1

    # Walk forward to the next terminator (inclusive).
    e = span_end
    while e < len(text) and text[e] not in ".!?\n":
        e += 1
    if e < len(text) and text[e] in ".!?":
        e += 1

    return s, e, text[s:e].strip()


def _check_long_sentences(page: ParsedPage) -> Iterable[RawSuggestion]:
    text = page.text
    cursor = 0
    for sentence in _RE_SENTENCE_SPLIT.split(text):
        start = text.find(sentence, cursor)
        if start < 0:
            cursor += len(sentence)
            continue
        cursor = start + len(sentence)
        words = sentence.split()
        if len(words) > _LONG_SENTENCE_THRESHOLD:
            preview = sentence.strip()
            if len(preview) > 200:
                preview = preview[:200] + "…"
            yield RawSuggestion(
                rule_kind="s1000d",
                rule_code="STE_LONG_SENTENCE",
                severity="warning",
                message=f"Phrase de {len(words)} mots — STE100 limite à {_LONG_SENTENCE_THRESHOLD}.",
                original=preview,
                proposed=preview,
                page=page.page,
                span=(start, start + len(preview)),
            )


def _check_passive_voice(page: ParsedPage) -> Iterable[RawSuggestion]:
    text = page.text
    seen: set[tuple[int, int]] = set()
    for m in _RE_PASSIVE.finditer(text):
        s, e, sentence = _expand_to_sentence(text, m.start(), m.end())
        if not sentence or (s, e) in seen:
            continue
        seen.add((s, e))
        yield RawSuggestion(
            rule_kind="s1000d",
            rule_code="STE_PASSIVE_VOICE",
            severity="info",
            message="Voix passive détectée — préférer la voix active à l'impératif.",
            original=sentence,
            proposed=sentence,
            page=page.page,
            span=(s, e),
        )


def _check_first_person(page: ParsedPage) -> Iterable[RawSuggestion]:
    text = page.text
    seen: set[tuple[int, int]] = set()
    for m in _RE_FIRST_PERSON.finditer(text):
        s, e, sentence = _expand_to_sentence(text, m.start(), m.end())
        if not sentence or (s, e) in seen:
            continue
        seen.add((s, e))
        yield RawSuggestion(
            rule_kind="s1000d",
            rule_code="STE_FIRST_PERSON",
            severity="warning",
            message="Première personne dans un manuel de maintenance — préférer la forme impersonnelle.",
            original=sentence,
            proposed=sentence,
            page=page.page,
            span=(s, e),
        )


def _check_gerund(page: ParsedPage) -> Iterable[RawSuggestion]:
    text = page.text
    seen: set[tuple[int, int]] = set()
    for m in _RE_GERUND_START.finditer(text):
        s, e, sentence = _expand_to_sentence(text, m.start(), m.end())
        if not sentence or (s, e) in seen:
            continue
        seen.add((s, e))
        yield RawSuggestion(
            rule_kind="s1000d",
            rule_code="STE_PROCEDURAL_GERUND",
            severity="info",
            message="Gérondif en début de procédure — réécrire à l'impératif.",
            original=sentence,
            proposed=sentence,
            page=page.page,
            span=(s, e),
        )


def _check_warning_format(page: ParsedPage) -> Iterable[RawSuggestion]:
    for m in _RE_WARNING_INLINE.finditer(page.text):
        yield RawSuggestion(
            rule_kind="s1000d",
            rule_code="S1000D_WARNING_FORMAT",
            severity="warning",
            message="Avertissement inline — déplacer sur une ligne dédiée en MAJUSCULES (S1000D 4.x).",
            original=m.group(0),
            proposed=m.group(0).upper(),
            page=page.page,
            span=m.span(),
        )


def _check_double_space(page: ParsedPage) -> Iterable[RawSuggestion]:
    for m in re.finditer(r"  +", page.text):
        yield RawSuggestion(
            rule_kind="s1000d",
            rule_code="S1000D_DOUBLE_SPACE",
            severity="info",
            message="Espaces doubles à éviter dans le contenu publié.",
            original=m.group(0),
            proposed=" ",
            page=page.page,
            span=m.span(),
        )


_CHECKS = {
    "STE_LONG_SENTENCE": _check_long_sentences,
    "STE_PASSIVE_VOICE": _check_passive_voice,
    "STE_FIRST_PERSON": _check_first_person,
    "STE_PROCEDURAL_GERUND": _check_gerund,
    "S1000D_WARNING_FORMAT": _check_warning_format,
    "S1000D_DOUBLE_SPACE": _check_double_space,
}


def run(pages: list[ParsedPage], disabled_codes: Iterable[str] = ()) -> list[RawSuggestion]:
    """Run every enabled S1000D / STE rule on every page."""
    skip = {c.strip().upper() for c in disabled_codes if c}
    suggestions: list[RawSuggestion] = []
    for page in pages:
        for code, check in _CHECKS.items():
            if code in skip:
                continue
            suggestions.extend(check(page))
    return suggestions
