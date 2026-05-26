"""ATA iSpec 2200 catalog — version 2018-1.

Successeur ATA 100, standard d'échange de données de maintenance
aéronautique civile (SGML/XML, références structurées).
"""

from __future__ import annotations

from app.checks.standards._base import StandardRule


_RULES_2018 = [
    StandardRule(
        code="ATA22_DMC_FORMAT",
        title="DMC iSpec 2200 bien formé",
        description=(
            "Le Data Module Code (DMC) iSpec 2200 suit le format "
            "MI-AC-AN-SY-SS-SU-DC-IC."
        ),
        kind="regex_flag",
        severity="warning",
        pattern=r"\bDMC[-\s][A-Z0-9]{2}-[A-Z0-9]{3}-[A-Z0-9]{2}-\d{2}-\d{2}",
        message="DMC iSpec 2200 — vérifier le format complet.",
    ),
    StandardRule(
        code="ATA22_FIELD_INFOCODE",
        title="Information Code renseigné",
        description=(
            "Tout DM doit porter son Information Code (3 chiffres) qui "
            "décrit la nature du contenu (procédure, description…)."
        ),
        kind="regex_flag",
        severity="warning",
        pattern=r"\bIC\s*[:=]?\s*\d{3}\b",
        message="Information Code manquant ou hors format (3 chiffres).",
    ),
    StandardRule(
        code="ATA22_FIELD_EFFECTIVITY",
        title="Applicability / Effectivity",
        description=(
            "iSpec 2200 §3.2 — toute procédure doit déclarer son "
            "applicabilité par modèle / MSN."
        ),
        kind="field_required",
        severity="error",
        pattern="Applicability|Effectivity|Effectivité",
        message="Champ « Applicability » obligatoire.",
    ),
    StandardRule(
        code="ATA22_FIELD_PERIODICITE",
        title="Périodicité tâche programmée",
        description=(
            "Interval (FH/FC/CAL) requis pour toute tâche de maintenance "
            "préventive."
        ),
        kind="field_required",
        severity="warning",
        pattern="Interval|Periodicity|Périodicité",
        message="Périodicité manquante (tâche préventive).",
        metadata={"conditional": "task_type=preventive"},
    ),
    StandardRule(
        code="ATA22_FIELD_DUREE",
        title="Elapsed time renseigné",
        description="Temps total estimé d'exécution.",
        kind="field_required",
        severity="info",
        pattern="Elapsed time|Duration|Durée",
        message="Champ « Elapsed time » manquant.",
    ),
    StandardRule(
        code="ATA22_FIELD_MANPOWER",
        title="Manpower / Skill level",
        description=(
            "Nombre et niveau de qualification des techniciens (A, B1, "
            "B2, C)."
        ),
        kind="field_required",
        severity="warning",
        pattern="Manpower|Skill level|Personnel",
        message="Champ « Manpower / Skill level » manquant.",
    ),
    StandardRule(
        code="ATA22_FIELD_NIVEAU",
        title="Maintenance level",
        description="Line / Base / Shop.",
        kind="enum_value",
        severity="warning",
        pattern="Line,Base,Shop",
        message="Maintenance level manquant ou hors énumération.",
        metadata={"field_label": "Maintenance level"},
    ),
    StandardRule(
        code="ATA22_SECTION_TOOLS",
        title="Required tools / equipment",
        description=(
            "Outillage requis listé en début de procédure (P/N + source)."
        ),
        kind="section_required",
        severity="warning",
        pattern="Required tools|Tools and equipment|Outillage",
        message="Section « Required tools » absente.",
    ),
    StandardRule(
        code="ATA22_SECTION_CONSUMABLES",
        title="Required consumables",
        description="Huiles, graisses, joints — listés explicitement.",
        kind="section_required",
        severity="warning",
        pattern="Required consumables|Consommables|Materials",
        message="Section « Required consumables » absente.",
    ),
    StandardRule(
        code="ATA22_SECTION_SPARES",
        title="Spare parts cohérents",
        description=(
            "Cohérence entre l'intitulé et les pièces (REPLACE → lister "
            "la pièce remplacée)."
        ),
        kind="field_consistency",
        severity="error",
        pattern="task=replace|install;spare=part|module|assembly",
        message="Spare parts incohérents avec l'intitulé de la tâche.",
    ),
    StandardRule(
        code="ATA22_SECTION_PRELIM",
        title="Preparation procedure",
        description=(
            "Mise en sécurité / consignation requise avant les étapes "
            "principales (préliminaires)."
        ),
        kind="section_required",
        severity="error",
        pattern="Preparation procedure|Safety precautions|Tâches préliminaires",
        message="Section « Preparation procedure » absente.",
    ),
    StandardRule(
        code="ATA22_SECTION_CLOSE",
        title="Close out procedure",
        description="Restitution + tests fonctionnels en fin de tâche.",
        kind="section_required",
        severity="error",
        pattern="Close out|Restoration|Post-maintenance|Functional test",
        message="Section « Close out » absente.",
    ),
    StandardRule(
        code="ATA22_STEP_VERB",
        title="Étape commençant par un verbe d'action",
        description=(
            "Chaque step doit débuter par un verbe à l'impératif / "
            "infinitif (« Remove », « Inspect », « Open »)."
        ),
        kind="step_pattern",
        severity="warning",
        pattern=r"^(?:[A-ZÀ-Ÿ][a-zà-ÿ]+(?:er|ir|re|oir)\b|[A-Z][a-z]{3,}(?:\s|$))",
        message="Step : commencer par un verbe d'action.",
    ),
    StandardRule(
        code="ATA22_NO_TBD",
        title="« TBD » à éliminer",
        description=(
            "Les placeholders « TBD », « TBC », « To Be Defined » "
            "doivent disparaître avant publication."
        ),
        kind="regex_flag",
        severity="error",
        pattern=r"\b(?:TBD|TBC|TBA|To Be Defined|To Be Confirmed)\b",
        message="Placeholder à résoudre avant publication.",
    ),
    StandardRule(
        code="ATA22_TORQUE_UNIT",
        title="Couple en N·m (SI primaire)",
        description=(
            "Le SI est l'unité primaire iSpec 2200. Les valeurs "
            "impériales doivent figurer entre parenthèses."
        ),
        kind="regex_flag",
        severity="info",
        pattern=r"\b\d+(?:\.\d+)?\s*(?:lb[·.]?ft|in[·.]?lb)\b(?!\s*\()",
        message="Couple impérial sans équivalent SI primaire.",
    ),
]


CATALOG: dict[str, list[StandardRule]] = {
    "2018-1": _RULES_2018,
}
