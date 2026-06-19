"""Catalogues builtin des standards supportes.

Par defaut, **seul ATA100** est present. Le seed importe `BUILTIN_STANDARDS`
pour peupler les tables `standards` / `standard_versions` au premier boot ; les
lectures runtime sont ensuite servies depuis la DB (l'utilisateur peut
cloner/surcharger). Les regles client viennent de l'import Excel, jamais d'ici.
"""

from __future__ import annotations

from app.checks.standards import ata100
from app.checks.standards._base import StandardRule


BUILTIN_STANDARDS: list[dict[str, object]] = [
    {
        "code": "ATA100",
        "label": "ATA 100 - Specification for manufacturers' technical data",
        "description": (
            "Chapitrage standard des manuels techniques aeronautiques civils "
            "(chapitre/section/sujet, references croisees, donnees techniques). "
            "Les controles propres au client proviennent de la checklist importee."
        ),
        "versions": ata100.CATALOG,
    },
]


__all__ = ["BUILTIN_STANDARDS", "StandardRule"]
