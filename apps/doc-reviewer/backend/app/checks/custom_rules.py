"""Apply user-defined regex / term rules from the `rules` table.

Supported `kind` values:

- `regex_replace` — `pattern` matched, `replacement` expanded with
  back-references (\\1, \\2…). Use for mechanical fixes.
- `term_replace` — case-insensitive literal match, `replacement` is the
  output string. Simpler than regex_replace for non-technical users.
- `regex_flag` — flag occurrences without proposing a fix; useful when
  the user only wants the location signalled.
- `case_capitalize` — match all-caps tokens (length >= 4) and propose the
  capitalised version (`WARNING` → `Warning`).
- `accent_fix` — match plain-ASCII French words and propose the accented
  form via the bundled lookup table (`deja` → `déjà`, `etre` → `être`…).

The detector returns one `RawSuggestion` per match. The caller
(`rules_engine.materialize`) computes bbox + span_index downstream.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.checks.s1000d_checks import RawSuggestion
from app.db.models import Rule
from app.parsers.pdf_parser import ParsedPage


# Mapping ASCII → accented for the seeded `accent_fix` rule. Static — we
# don't try to be exhaustive; the user can Reject for false positives.
_ACCENT_MAP: dict[str, str] = {
    "deja": "déjà",
    "etre": "être",
    "ete": "été",
    "tres": "très",
    "apres": "après",
    "systeme": "système",
    "securite": "sécurité",
    "verifier": "vérifier",
    "operation": "opération",
    "piece": "pièce",
    "necessite": "nécessite",
    "interet": "intérêt",
    "element": "élément",
    "donnee": "donnée",
    "donnees": "données",
    "reglage": "réglage",
    "reglages": "réglages",
    "controle": "contrôle",
    "procedure": "procédure",
    "generale": "générale",
    "general": "général",
    "specifique": "spécifique",
    "electrique": "électrique",
    "mecanique": "mécanique",
    "hydraulique": "hydraulique",
    "preciser": "préciser",
}


def _propose_capitalize(word: str) -> str:
    """Convert an ALL-CAPS word OR phrase to French sentence case.

    Sentence case (used in technical procedure headings) capitalises
    only the first word and keeps everything else lowercase :

    - `WARNING` → `Warning`
    - `PROCÉDURE DE MAINTENANCE` → `Procédure de maintenance`
    - `DEMONTAGE DU MOTEUR` → `Demontage du moteur`

    Short tokens (< 4 chars) are kept as-is when they appear alone —
    they're usually acronyms (`USB`, `API`, `CRC`…). In a multi-word
    phrase, embedded short tokens are forced to lowercase too, which
    is wrong for « Rolls-Royce »-like proper nouns ; the user can
    edit before accepting in that edge case."""
    if len(word) < 4:
        return word
    tokens = word.split()
    if len(tokens) == 1:
        return tokens[0][0].upper() + tokens[0][1:].lower()
    out: list[str] = []
    for i, tok in enumerate(tokens):
        if i == 0:
            out.append(tok[0].upper() + tok[1:].lower())
        else:
            out.append(tok.lower())
    return " ".join(out)


def _propose_accent(word: str) -> str:
    """Lookup in `_ACCENT_MAP`, preserving the original capitalisation."""
    accented = _ACCENT_MAP.get(word.lower())
    if not accented:
        return word
    if word[0].isupper():
        return accented[0].upper() + accented[1:]
    return accented


def _propose(rule: Rule, match: re.Match[str]) -> str:
    original = match.group(0)
    kind = rule.kind
    if kind == "regex_flag":
        # Flag-only — keep original; the UI exposes "Edit" so the user can
        # propose a fix manually.
        return original
    if kind == "term_replace":
        return rule.replacement
    if kind == "case_capitalize":
        return _propose_capitalize(original)
    if kind == "accent_fix":
        return _propose_accent(original)
    # Default: regex_replace
    try:
        return match.expand(rule.replacement) if rule.replacement else original
    except re.error:
        return rule.replacement or original


# Kinds handled deterministically here. Natural-language checklist rules
# (`llm_nl`) carry a French consigne in `pattern`, NOT a regex — they are
# judged by Mistral in `rules_engine._run_ai_custom` and must be skipped here
# (else `re.compile` would substring-match the consigne text against the doc).
_DETERMINISTIC_KINDS = {
    "regex_replace",
    "term_replace",
    "regex_flag",
    "case_capitalize",
    "accent_fix",
}


def run(rules: Iterable[Rule], pages: list[ParsedPage]) -> list[RawSuggestion]:
    suggestions: list[RawSuggestion] = []
    enabled = [r for r in rules if r.enabled and r.kind in _DETERMINISTIC_KINDS]
    for rule in enabled:
        try:
            flags = re.IGNORECASE if rule.kind in {"term_replace", "accent_fix"} else 0
            pattern = re.compile(rule.pattern, flags)
        except re.error:
            continue
        for page in pages:
            for m in pattern.finditer(page.text):
                proposed = _propose(rule, m)
                suggestions.append(
                    RawSuggestion(
                        rule_kind="custom",
                        rule_code=f"CUSTOM_{rule.id.hex[:8].upper()}",
                        severity=rule.severity or "warning",
                        message=rule.message or rule.name,
                        original=m.group(0),
                        proposed=proposed,
                        page=page.page,
                        span=m.span(),
                    )
                )
    return suggestions
