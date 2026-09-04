"""MAT10000 (Dassault Aviation) catalog — version 1.

Référentiel Dassault de description des tâches de maintenance. Les
règles ci-dessous combinent vérifications structurelles (champs
obligatoires, sections requises, format des étapes) et règles textuelles
(terminologie, formats de référence).
"""

from __future__ import annotations

from app.checks.standards._base import StandardRule


_RULES_V1 = [
    StandardRule(
        code="MAT_FIELD_PERIODICITE",
        title="Périodicité renseignée",
        description=(
            "Pour toute tâche de maintenance préventive, la périodicité "
            "(heures de vol, cycles, calendaire) doit être explicitement "
            "renseignée."
        ),
        kind="field_required",
        severity="error",
        pattern="Périodicité|Periodicity|Interval",
        message="Champ « Périodicité » obligatoire pour la maintenance préventive.",
        metadata={"conditional": "task_type=preventive"},
    ),
    StandardRule(
        code="MAT_FIELD_DUREE",
        title="Durée de la procédure",
        description=(
            "La durée estimée de la procédure (en minutes ou h/min) "
            "doit être renseignée pour le planning de maintenance."
        ),
        kind="field_required",
        severity="warning",
        pattern="Durée|Duration|Elapsed time",
        message="Champ « Durée » manquant.",
    ),
    StandardRule(
        code="MAT_FIELD_PERSONNEL",
        title="Personnel nécessaire",
        description=(
            "Nombre et qualification des opérateurs requis "
            "(ex : 1 mécanicien B1, 1 inspecteur)."
        ),
        kind="field_required",
        severity="warning",
        pattern="Personnel|Manpower|Crew",
        message="Champ « Personnel nécessaire » manquant.",
    ),
    StandardRule(
        code="MAT_FIELD_NIVEAU",
        title="Niveau de maintenance",
        description=(
            "Niveau de maintenance (NTI-1 / NTI-2 / NTI-3, ou Line / "
            "Base / Shop). Valeur énumérée."
        ),
        kind="enum_value",
        severity="error",
        pattern="NTI-1,NTI-2,NTI-3,Line,Base,Shop",
        message="Niveau de maintenance manquant ou hors énumération.",
        metadata={"field_label": "Niveau de maintenance"},
    ),
    StandardRule(
        code="MAT_SECTION_EQUIPEMENT",
        title="Équipement de soutien listé",
        description=(
            "Section listant l'outillage et l'équipement de soutien "
            "nécessaires (tournevis, clé dynamométrique, banc de test…)."
        ),
        kind="section_required",
        severity="warning",
        pattern="Équipement de soutien|Outillage|Support equipment|Tools",
        message="Section « Équipement de soutien » absente.",
    ),
    StandardRule(
        code="MAT_SECTION_CONSOMMABLES",
        title="Consommables listés",
        description=(
            "Liste des consommables nécessaires (huile, graisse, "
            "lockwire, joints, vernis frein)."
        ),
        kind="section_required",
        severity="warning",
        pattern="Consommables|Consumables|Materials",
        message="Section « Consommables » absente.",
    ),
    StandardRule(
        code="MAT_SECTION_RECHANGE",
        title="Pièces de rechange listées",
        description=(
            "Pièces de rechange (PN/SN) listées avec quantité. Doit être "
            "cohérent avec l'intitulé de la tâche : si la tâche est "
            "« Remplacer le moteur », la rechange doit lister un moteur."
        ),
        kind="field_consistency",
        severity="error",
        pattern="task=replace|remplacer;spare=engine|moteur|pump|pompe|filter|filtre",
        message="Pièce de rechange incohérente avec l'intitulé de la tâche.",
    ),
    StandardRule(
        code="MAT_SECTION_PRELIM",
        title="Tâches préliminaires",
        description=(
            "Consignations, mises en sécurité, préparations à effectuer "
            "avant les étapes principales."
        ),
        kind="section_required",
        severity="error",
        pattern="Tâches préliminaires|Préliminaires|Preliminary tasks|Safety",
        message="Section « Tâches préliminaires » absente.",
    ),
    StandardRule(
        code="MAT_SECTION_POST",
        title="Tâches post-maintenance",
        description=(
            "Tests fonctionnels, déconsignation, remise en configuration "
            "vol après les étapes principales."
        ),
        kind="section_required",
        severity="error",
        pattern="Tâches post-maintenance|Restitution|Post-maintenance|Functional test",
        message="Section « Tâches post-maintenance » absente.",
    ),
    StandardRule(
        code="MAT_STEP_VERB",
        title="Étape commençant par un verbe à l'infinitif",
        description=(
            "Chaque étape numérotée doit commencer par un verbe à "
            "l'infinitif (« Retirer », « Vérifier », « Remove », "
            "« Inspect »). Phrases nominales et sujets explicites sont "
            "prohibés."
        ),
        kind="step_pattern",
        severity="warning",
        pattern=r"^(?:[A-ZÀ-Ÿ][a-zà-ÿ]+(?:er|ir|re|oir)\b|[A-Z][a-z]{3,}(?:\s|$))",
        message="Étape : verbe à l'infinitif requis.",
        example_invalid="1. Le panneau est retiré.",
        example_valid="1. Retirer le panneau.",
    ),
    StandardRule(
        code="MAT_REF_FORMAT",
        title="Référence MAT10000 formatée",
        description=(
            "Les renvois vers une autre tâche MAT10000 doivent suivre le "
            "format MAT-XX-YY-ZZ-NNN."
        ),
        kind="regex_flag",
        severity="info",
        pattern=r"\bMAT-\d{2}-\d{2}-\d{2}-\d{3}\b",
        message="Référence MAT10000 — vérifier le format MAT-XX-YY-ZZ-NNN.",
    ),
    StandardRule(
        code="MAT_NO_PASSIVE",
        title="Voix passive interdite dans les étapes",
        description="Les étapes doivent être à l'impératif actif.",
        kind="regex_flag",
        severity="warning",
        pattern=r"\b(?:est|sont|a été|ont été|doit être|doivent être)\s+\w+(?:é|és|ée|ées)\b",
        message="Voix passive — réécrire à l'impératif actif.",
    ),
    StandardRule(
        code="MAT_TERMINOLOGY_DANGER",
        title="Terminologie DANGER / WARNING / CAUTION",
        description=(
            "Hiérarchie obligatoire : DANGER (mort possible) > WARNING "
            "(blessure possible) > CAUTION (dommage matériel). Les "
            "synonymes (« Attention », « Important ») sont prohibés."
        ),
        kind="term_replace",
        severity="warning",
        pattern=r"\b(Attention|Important)\b",
        replacement="CAUTION",
        message="Préférer DANGER / WARNING / CAUTION (hiérarchie MAT10000).",
    ),
    StandardRule(
        code="MAT_TORQUE_UNIT",
        title="Couple de serrage en N·m",
        description=(
            "Les couples de serrage sont exprimés en N·m. Les unités "
            "impériales (lb·ft, in·lb) doivent être converties ou "
            "annotées entre parenthèses."
        ),
        kind="regex_flag",
        severity="info",
        pattern=r"\b\d+(?:\.\d+)?\s*(?:lb[·.]?ft|in[·.]?lb)\b",
        message="Couple en unités impériales — convertir en N·m.",
    ),
]


CATALOG: dict[str, list[StandardRule]] = {
    "v1": _RULES_V1,
}
