"""Built-in catalogs for the supported documentation standards.

Each submodule exports a `CATALOG: dict[version_label, list[StandardRule]]`
mapping a published version to its rule set. The Alembic seed migration
imports `BUILTIN_STANDARDS` to populate the `standards` /
`standard_versions` tables on first boot — runtime reads are then served
from the DB so the user can clone/override built-in catalogs.
"""

from __future__ import annotations

from app.checks.standards import ata100, ata2200, mat10000, s1000d, s2000m, ste100
from app.checks.standards._base import StandardRule


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
        "code": "S1000D",
        "label": "S1000D — Aerospace technical publication standard",
        "description": (
            "Norme de structure documentaire ASD/AIA pour la "
            "documentation technique aéronautique modulaire (Data "
            "Modules, DMC, BREX, IETP). Pour les règles de style "
            "rédactionnel, voir la norme distincte ASD-STE100."
        ),
        "versions": s1000d.CATALOG,
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
        "code": "S2000M",
        "label": "S2000M — Material management spec (ASD/AIA)",
        "description": (
            "Standard international pour la gestion des matériels et "
            "rechanges. Couvre la nomenclature, les codes de "
            "maintenance, les listes de pièces."
        ),
        "versions": s2000m.CATALOG,
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
    {
        "code": "ATA2200",
        "label": "ATA iSpec 2200 — Information standards for aviation maintenance",
        "description": (
            "Successeur ATA 100 : standard d'échange de données de "
            "maintenance aéronautique civile, SGML/XML, références "
            "structurées."
        ),
        "versions": ata2200.CATALOG,
    },
]


__all__ = ["BUILTIN_STANDARDS", "StandardRule"]
