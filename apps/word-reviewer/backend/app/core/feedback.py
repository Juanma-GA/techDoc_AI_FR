"""Boucle de feedback relecteur -> catalogue (couche 4 de fiabilisation).

Les findings explicitement **rejetes** par le relecteur alimentent une liste
d'**exclusions** `(rule_code, original_text)` reinjectee a l'analyse suivante :
un faux positif recurrent ne re-apparait pas. Simple et persistant tant que la
suggestion rejetee existe en base.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.checks.raw import RawSuggestion
from app.db.models import Suggestion


def load_exclusions(db: Session) -> set[tuple[str, str]]:
    rows = db.execute(
        select(Suggestion.rule_code, Suggestion.original_text).where(
            Suggestion.status == "rejected"
        )
    ).all()
    return {(rc, ot) for rc, ot in rows if ot}


def filter_excluded(
    raws: list[RawSuggestion], exclusions: set[tuple[str, str]]
) -> list[RawSuggestion]:
    if not exclusions:
        return raws
    return [r for r in raws if (r.rule_code, r.original) not in exclusions]
