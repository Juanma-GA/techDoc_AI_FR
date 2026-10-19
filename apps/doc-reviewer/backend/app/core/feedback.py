"""Boucle de feedback relecteur -> analyse (fiabilisation, couche globale).

Porté de word-reviewer. Les findings explicitement **rejetés** par le relecteur
(motif de rejet saisi) alimentent une liste d'**exclusions** `(rule_code,
original_text)` réinjectée aux analyses suivantes du même mode : un faux positif
récurrent ne ré-apparaît pas sur les documents normaux ou sur les documents
démo, sans partager les exclusions entre ces deux périmètres.

Portée volontairement restreinte aux findings **détectés par l'IA** (`AI_SCAN`) :
le déterministe (regex/structural/units/layout) est certain et ne doit pas être
supprimé globalement par un rejet ponctuel.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.checks.raw import RawSuggestion
from app.core.demo_mode import get_demo_enabled
from app.db.models import Document, Suggestion

# Codes de findings soumis au feedback global (IA uniquement).
LLM_CODES = {"AI_SCAN"}


def load_exclusions(db: Session) -> set[tuple[str, str]]:
    """Rejected `(rule_code, original_text)` signatures in the current mode."""
    rows = db.execute(
        select(Suggestion.rule_code, Suggestion.original_text)
        .join(Document, Suggestion.document_id == Document.id)
        .where(
            Suggestion.status == "rejected",
            Suggestion.rule_code.in_(LLM_CODES),
            Document.is_demo.is_(get_demo_enabled(db)),
        )
    ).all()
    return {(rc, ot) for rc, ot in rows if ot}


def filter_excluded(
    raws: list[RawSuggestion], exclusions: set[tuple[str, str]]
) -> list[RawSuggestion]:
    """Retire les findings IA dont la signature est globalement rejetée. Les
    findings déterministes ne sont jamais filtrés ici."""
    if not exclusions:
        return raws
    return [
        r
        for r in raws
        if r.rule_code not in LLM_CODES or (r.rule_code, r.original) not in exclusions
    ]
