"""Portail qualité : mesure de revuabilité homogène, tous formats confondus.

Quel que soit le format d'entrée (PDF natif, Word/`.doc`/`.docx` converti), la
revue tourne sur le **même** PDF normalisé. Mais un PDF sans couche texte (scan,
ou conversion d'un document image) produit une revue **vide silencieusement** —
un « faux conforme », le pire risque d'hétérogénéité entre documents. Ce module
mesure la couverture texte et classe le document :

- `analyzable` : couche texte suffisante → revue fiable.
- `degraded`   : texte partiel (certaines pages sans texte extractible) →
                 revue possible mais incomplète, à signaler.
- `unusable`   : aucune couche texte (scanné / image) → revue non fiable ;
                 à signaler EXPLICITEMENT plutôt que de rendre zéro anomalie.

Pas d'OCR dans ce POC : un `unusable` doit être repris à la source (fournir un
PDF avec couche texte, ou ré-exporter le Word). Voir `parsers.pdf_parser`.
"""

from __future__ import annotations

from dataclasses import dataclass

# En dessous de ce % de pages porteuses de texte, le document est « dégradé »
# (une partie significative n'a pas pu être analysée).
_DEGRADED_MIN_COVERAGE = 60

STATE_ANALYZABLE = "analyzable"
STATE_DEGRADED = "degraded"
STATE_UNUSABLE = "unusable"


@dataclass
class QualityReport:
    coverage: int  # % de pages porteuses d'une couche texte (0-100)
    pages_with_text: int
    page_count: int
    state: str  # analyzable | degraded | unusable


def assess(doc) -> QualityReport:
    """Évalue la revuabilité d'un `fitz.Document` déjà ouvert.

    Ne referme pas `doc` (l'appelant en garde la propriété)."""
    page_count = int(getattr(doc, "page_count", 0) or 0)
    if page_count == 0:
        return QualityReport(0, 0, 0, STATE_UNUSABLE)

    pages_with_text = 0
    for page in doc:
        text = page.get_text("text") or ""
        if text.strip():
            pages_with_text += 1

    coverage = round(100 * pages_with_text / page_count)
    if pages_with_text == 0:
        state = STATE_UNUSABLE
    elif coverage < _DEGRADED_MIN_COVERAGE:
        state = STATE_DEGRADED
    else:
        state = STATE_ANALYZABLE
    return QualityReport(coverage, pages_with_text, page_count, state)
