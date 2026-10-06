"""Transport type partagé par tous les checks.

`RawSuggestion` est la structure neutre qu'émet chaque détecteur (catalogue,
custom, layout, units, vision, style) avant matérialisation en `Suggestion`
ORM par `rules_engine.materialize`. Elle vivait historiquement dans
`s1000d_checks.py` (module retiré) ; elle est désormais ici, sans dépendance
vers un check particulier.
"""

from __future__ import annotations

from dataclasses import dataclass


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
    ai_generated: bool = False
