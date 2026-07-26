"""ATA 100 catalog — revision 38 (last published).

Chapitrage standard des manuels techniques aéronautiques civils.
Couvre l'usage des chapitres (chapter / section / subject) et les
références croisées.
"""

from __future__ import annotations

from app.checks.standards._base import StandardRule


_RULES_REV38 = [
    StandardRule(
        code="ATA_CHAPTER_REF",
        title="Référence chapitre ATA bien formée",
        description=(
            "Les renvois doivent suivre le format chapitre-section-sujet "
            "(ex : 24-21-00). Le tiret est obligatoire."
        ),
        kind="regex_flag",
        severity="warning",
        pattern=r"\b\d{2}-\d{2}-\d{2}\b",
        message="Référence ATA — vérifier le format CH-SE-SU.",
    ),
    StandardRule(
        code="ATA_CHAPTER_RANGE",
        title="Chapitre ATA dans l'intervalle 0-99",
        description=(
            "Le chapitre principal ATA 100 est numéroté de 00 (général) "
            "à 99. Toute valeur hors plage est invalide."
        ),
        kind="regex_flag",
        severity="error",
        pattern=r"\bCh(?:apter|apitre)\s+(?:[1-9]\d{2,}|0?[a-zA-Z])",
        message="Chapitre ATA hors plage 00-99.",
    ),
    StandardRule(
        code="ATA_FIELD_EFFECTIVITY",
        title="Effectivité (Effectivity) renseignée",
        description=(
            "Toute procédure doit déclarer son effectivité "
            "(série/configuration applicable)."
        ),
        kind="field_required",
        severity="warning",
        pattern="Effectivity|Effectivité|Applicability",
        message="Champ « Effectivity » manquant.",
    ),
    StandardRule(
        code="ATA_FIELD_PERIODICITE",
        title="Périodicité (preventive)",
        description=(
            "Pour les tâches de maintenance programmée, la fréquence "
            "(FH / FC / CAL) doit être indiquée."
        ),
        kind="field_required",
        severity="warning",
        pattern="Interval|Periodicity|Périodicité|Frequency",
        message="Champ « Périodicité » manquant pour une tâche programmée.",
        metadata={"conditional": "task_type=preventive"},
    ),
    StandardRule(
        code="ATA_FIELD_DUREE",
        title="Durée de la procédure",
        description="Elapsed time / man-hours requis pour le planning.",
        kind="field_required",
        severity="info",
        pattern="Duration|Elapsed time|Durée|Man-hours",
        message="Champ « Durée » manquant.",
    ),
    StandardRule(
        code="ATA_FIELD_PERSONNEL",
        title="Personnel (manpower) listé",
        description="Nombre et qualification des techniciens requis.",
        kind="field_required",
        severity="info",
        pattern="Manpower|Personnel|Crew|Skill level",
        message="Champ « Personnel » manquant.",
    ),
    StandardRule(
        code="ATA_FIELD_NIVEAU",
        title="Niveau de maintenance",
        description=(
            "Line / Base / Shop selon l'environnement d'exécution prévu."
        ),
        kind="enum_value",
        severity="warning",
        pattern="Line,Base,Shop",
        message="Niveau de maintenance manquant ou hors énumération.",
        metadata={"field_label": "Maintenance level"},
    ),
    StandardRule(
        code="ATA_SECTION_TOOLS",
        title="Tools and equipment listés",
        description=(
            "Section listant l'outillage requis (P/N, source) — "
            "obligatoire dans toute procédure ATA."
        ),
        kind="section_required",
        severity="warning",
        pattern="Tools and equipment|Outillage|Tooling",
        message="Section « Tools and equipment » absente.",
    ),
    StandardRule(
        code="ATA_SECTION_CONSUMABLES",
        title="Consumables listés",
        description="Huiles, graisses, joints, frein-filets…",
        kind="section_required",
        severity="warning",
        pattern="Consumables|Consommables|Materials",
        message="Section « Consumables » absente.",
    ),
    StandardRule(
        code="ATA_SECTION_SPARES",
        title="Spare parts cohérents avec la tâche",
        description=(
            "Cohérence entre l'intitulé (REPLACE / REMOVE / INSTALL) et "
            "la liste de rechange : un REPLACE doit lister une pièce de "
            "même nature que l'élément remplacé."
        ),
        kind="field_consistency",
        severity="error",
        pattern="task=replace|remove|install;spare=part|assembly|module",
        message="Spare parts incohérents avec l'intitulé de la tâche.",
    ),
    StandardRule(
        code="ATA_SECTION_PRELIM",
        title="Preliminary procedure / safety",
        description=(
            "Section de mise en sécurité (consignation, protection "
            "personnelle) avant les étapes principales."
        ),
        kind="section_required",
        severity="error",
        pattern="Preliminary|Safety precautions|Tâches préliminaires|Consignation",
        message="Section « Preliminary / Safety » absente.",
    ),
    StandardRule(
        code="ATA_SECTION_CLOSE",
        title="Close out / post-maintenance",
        description=(
            "Section de remise en configuration vol et tests "
            "fonctionnels en fin de procédure."
        ),
        kind="section_required",
        severity="error",
        pattern="Close out|Restoration|Post-maintenance|Functional test",
        message="Section « Close out / post-maintenance » absente.",
    ),
    StandardRule(
        code="ATA_STEP_VERB",
        title="Étape commençant par un verbe à l'infinitif",
        description=(
            "Chaque étape numérotée doit commencer par un verbe d'action "
            "à l'impératif/infinitif (« Remove », « Inspect », "
            "« Verify »)."
        ),
        kind="step_pattern",
        severity="warning",
        pattern=r"^(?:[A-ZÀ-Ÿ][a-zà-ÿ]+(?:er|ir|re|oir)\b|[A-Z][a-z]{3,}(?:\s|$))",
        message="Étape : verbe à l'infinitif requis.",
    ),
    StandardRule(
        code="ATA_NO_AMBIGUOUS_QUANT",
        title="Quantificateurs ambigus à éviter",
        description=(
            "Éviter « some », « a few », « several » — préférer une "
            "quantité chiffrée."
        ),
        kind="regex_flag",
        severity="info",
        pattern=r"\b(?:some|a few|several|plusieurs)\b",
        message="Quantificateur ambigu — préférer une valeur chiffrée.",
    ),
    StandardRule(
        code="ATA_TORQUE_DUAL_UNIT",
        title="Couple en unité duale (N·m + lb·ft)",
        description=(
            "Les valeurs de couple doivent être présentées dans les deux "
            "unités (SI primaire, impérial secondaire)."
        ),
        kind="regex_flag",
        severity="info",
        pattern=r"\b\d+(?:\.\d+)?\s*(?:N[·.]?m|lb[·.]?ft)\b",
        message="Couple — vérifier la présence des deux unités (N·m / lb·ft).",
    ),
]


CATALOG: dict[str, list[StandardRule]] = {
    "rev 38": _RULES_REV38,
}
