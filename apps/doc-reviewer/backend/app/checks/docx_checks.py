"""Contrôles **Word natifs** (pipeline docx) — impossibles sur un PDF.

Portés de word-reviewer. S'appuient sur les métadonnées de `docx_parser.Block`
(suivi de modifications, zones sémantiques) qu'un rendu PDF perd :

- **Barres de révision** (`revision_bar_check`) : signale les blocs porteurs
  d'une modification suivie (`w:ins`/`w:del`/format) — le relecteur doit
  vérifier que la barre de révision (`w:pBdr`) est bien posée.

Émettent des `RawSuggestion` **détection-only** (`proposed=""`), localisées par
bloc (`page = block.index` → `target_id = dp<index>` à la matérialisation).
"""

from __future__ import annotations

from app.checks.raw import RawSuggestion
from app.parsers.docx_parser import ParsedDocx

_REVISION_KINDS = {"ins", "del", "fmt"}
_KIND_LABEL = {
    "ins": "insertion suivie",
    "del": "suppression suivie",
    "fmt": "changement de format suivi",
}


def revision_bar_check(parsed: ParsedDocx) -> list[RawSuggestion]:
    """Signale chaque bloc portant une modification suivie (à vérifier vs barre
    de révision). Un bloc déjà marqué `bar` (pBdr sans ins/del) n'est pas
    signalé."""
    out: list[RawSuggestion] = []
    for block in parsed.blocks:
        if block.revision_kind in _REVISION_KINDS:
            label = _KIND_LABEL.get(block.revision_kind or "", "modification suivie")
            preview = (block.text or "").strip()[:160]
            out.append(
                RawSuggestion(
                    rule_kind="standard",
                    rule_code="DOCX_REVISION_BAR",
                    severity="warning",
                    message=f"Bloc en {label} — vérifier la barre de révision.",
                    original=preview,
                    proposed="",  # détection-only
                    page=block.index,
                    span=(0, len(preview)),
                )
            )
    return out


def run(parsed: ParsedDocx) -> list[RawSuggestion]:
    """Exécute tous les checks Word natifs sur un `ParsedDocx`."""
    out: list[RawSuggestion] = []
    out.extend(revision_bar_check(parsed))
    return out
