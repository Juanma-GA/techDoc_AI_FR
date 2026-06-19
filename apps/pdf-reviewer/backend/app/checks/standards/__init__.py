"""Built-in catalogs for the supported documentation standards.

Each submodule exports a `CATALOG: dict[version_label, list[StandardRule]]`
mapping a published version to its rule set. The Alembic seed migration
imports `BUILTIN_STANDARDS` to populate the `standards` /
`standard_versions` tables on first boot — runtime reads are then served
from the DB so the user can clone/override built-in catalogs.
"""

from __future__ import annotations

from app.checks.standards import ata100, mat10000, ste100
from app.checks.standards._base import StandardRule


# Le PDF Reviewer analyse le **rendu PDF** publié, jamais la source. Les
# normes purement XML/gestion de données (S1000D, ATA iSpec 2200, S2000M)
# ont été retirées du catalogue : leurs règles vérifiaient des champs/codes
# (DMC, NSN, CAGE, Information Code, SMR, QPA…) qui n'existent que dans le
# XML/SGML source et n'ont pas de sens sur un PDF. Seules restent les normes
# dont les règles portent sur le texte/rendu : ASD-STE100 (style), MAT10000
# (description de tâche) et ATA 100 (chapitrage). Les règles de style
# rédactionnel S1000D/STE conservées vivent dans `app.checks.s1000d_checks`
# (moteur transverse toujours actif).
BUILTIN_STANDARDS: list[dict[str, object]] = [
    {
        "code": "ASD-STE100",
        "label": "ASD-STE100 — Simplified Technical English",
        "description": (
            "Norme de style d'écriture maintenue par ASD (AeroSpace and "
            "Defence Industries Association of Europe). Vocabulaire "
            "approuvé, voix active, phrases courtes, première personne "
            "interdite, gérondif proscrit. Référencée par S1000D mais "
            "indépendante."
        ),
        "versions": ste100.CATALOG,
    },
    {
        "code": "MAT10000",
        "label": "MAT10000 — Maintenance task description (Dassault Aviation)",
        "description": (
            "Référentiel Dassault pour la description des tâches de "
            "maintenance : structure de procédure, ressources requises, "
            "consignes de sécurité."
        ),
        "versions": mat10000.CATALOG,
    },
    {
        "code": "ATA100",
        "label": "ATA 100 — Specification for manufacturers' technical data",
        "description": (
            "Chapitrage standard des manuels techniques aéronautiques "
            "civils (chapitre/section/sujet). Format historique remplacé "
            "par iSpec 2200 mais toujours référencé."
        ),
        "versions": ata100.CATALOG,
    },
]


__all__ = ["BUILTIN_STANDARDS", "StandardRule"]
