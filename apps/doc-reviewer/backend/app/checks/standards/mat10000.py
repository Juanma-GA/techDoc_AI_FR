"""MAT10000 version 1 catalog, expressed with the existing CompiledRule contract."""

from __future__ import annotations

from app.core.compiled_rules import Check, CompiledRule, RuleTarget


_TARGET = RuleTarget(page="all", region="full_page")
_ORIGIN = "MAT10000:v1"


def _rule(code: str, topic: str, pattern: str) -> CompiledRule:
    return CompiledRule(
        id=code,
        topic=topic,
        execution="deterministic",
        target=_TARGET,
        checks=[Check(field="text", operator="regex", expected=pattern)],
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:{code}",
    )


_RULES_V1 = [
    _rule(
        "MAT_FIELD_PERIODICITE",
        "Périodicité renseignée",
        r"(?is)^(?=.*\b(?:preventive|scheduled|periodic|maintenance préventive|maintenance preventive)\b)(?!.*\b(?:Périodicité|Periodicity|Interval)\b).*$",
    ),
    _rule(
        "MAT_FIELD_DUREE",
        "Durée de la procédure",
        r"(?is)^(?!.*\b(?:Durée|Duration|Elapsed time)\b).*$",
    ),
    _rule(
        "MAT_FIELD_PERSONNEL",
        "Personnel nécessaire",
        r"(?is)^(?!.*\b(?:Personnel|Manpower|Crew)\b).*$",
    ),
    _rule(
        "MAT_FIELD_NIVEAU",
        "Niveau de maintenance",
        r"(?is)^(?!.*\b(?:Niveau de maintenance|Maintenance level)\s*[:=]\s*(?:NTI-[123]|Line|Base|Shop)\b).*$",
    ),
    _rule(
        "MAT_SECTION_EQUIPEMENT",
        "Équipement de soutien listé",
        r"(?is)^(?!.*\b(?:Équipement de soutien|Equipement de soutien|Outillage|Support equipment|Tools)\b).*$",
    ),
    _rule(
        "MAT_SECTION_CONSOMMABLES",
        "Consommables listés",
        r"(?is)^(?!.*\b(?:Consommables|Consumables|Materials)\b).*$",
    ),
    _rule(
        "MAT_SECTION_RECHANGE",
        "Pièces de rechange listées",
        r"(?is)^(?=.*\b(?:replace|remplacer|remove|déposer|install|installer)\b)(?!.*\b(?:engine|moteur|pump|pompe|filter|filtre|spare|rechange|part|pièce|piece)\b).*$",
    ),
    _rule(
        "MAT_SECTION_PRELIM",
        "Tâches préliminaires",
        r"(?is)^(?!.*\b(?:Tâches préliminaires|Tâches preliminaires|Préliminaires|Preliminary tasks|Safety)\b).*$",
    ),
    _rule(
        "MAT_SECTION_POST",
        "Tâches post-maintenance",
        r"(?is)^(?!.*\b(?:Tâches post-maintenance|Restitution|Post-maintenance|Functional test)\b).*$",
    ),
    _rule(
        "MAT_STEP_VERB",
        "Étape commençant par un verbe à l'infinitif",
        r"(?im)^\s*(?:(?:Step|Étape|Etape)\s+)?\(?\d+[.)\]]\s+(?!(?:Remove|Inspect|Verify|Install|Replace|Disconnect|Connect|Open|Close|Check|Clean|Measure|Adjust|Set|Record|Ensure|Retirer|Inspecter|Vérifier|Installer|Remplacer|Déposer|Déconnecter|Connecter|Ouvrir|Fermer|Contrôler|Nettoyer|Mesurer|Régler|Noter)\b|[A-ZÀ-Ÿ][a-zà-ÿ]+(?:er|ir|re|oir)\b).+",
    ),
    _rule(
        "MAT_REF_FORMAT",
        "Référence MAT10000 formatée",
        r"\bMAT-(?!\d{2}-\d{2}-\d{2}-\d{3}\b)[A-Za-z0-9.-]+",
    ),
    _rule(
        "MAT_NO_PASSIVE",
        "Voix passive interdite dans les étapes",
        r"(?i)\b(?:est|sont|a été|ont été|doit être|doivent être)\s+\w+(?:é|és|ée|ées|ed|en)\b",
    ),
    _rule(
        "MAT_TERMINOLOGY_DANGER",
        "Terminologie DANGER / WARNING / CAUTION",
        r"(?i)\b(?:Attention|Important)\b",
    ),
    _rule(
        "MAT_TORQUE_UNIT",
        "Couple de serrage en N·m",
        r"\b\d+(?:\.\d+)?\s*(?:lb[·.]?ft|in[·.]?lb)\b",
    ),
]


RULE_METADATA = {
    "MAT_FIELD_PERIODICITE": {"description": "Pour toute tâche de maintenance préventive, la périodicité doit être explicitement renseignée.", "kind": "field_required", "severity": "error", "message": "Champ « Périodicité » obligatoire pour la maintenance préventive.", "metadata": {"conditional": "task_type=preventive"}},
    "MAT_FIELD_DUREE": {"description": "La durée estimée de la procédure doit être renseignée pour le planning de maintenance.", "kind": "field_required", "severity": "warning", "message": "Champ « Durée » manquant."},
    "MAT_FIELD_PERSONNEL": {"description": "Nombre et qualification des opérateurs requis.", "kind": "field_required", "severity": "warning", "message": "Champ « Personnel nécessaire » manquant."},
    "MAT_FIELD_NIVEAU": {"description": "Niveau de maintenance NTI-1 / NTI-2 / NTI-3, ou Line / Base / Shop.", "kind": "enum_value", "severity": "error", "message": "Niveau de maintenance manquant ou hors énumération.", "metadata": {"field_label": "Niveau de maintenance"}},
    "MAT_SECTION_EQUIPEMENT": {"description": "Section listant l'outillage et l'équipement de soutien nécessaires.", "kind": "section_required", "severity": "warning", "message": "Section « Équipement de soutien » absente."},
    "MAT_SECTION_CONSOMMABLES": {"description": "Liste des consommables nécessaires.", "kind": "section_required", "severity": "warning", "message": "Section « Consommables » absente."},
    "MAT_SECTION_RECHANGE": {"description": "Pièces de rechange listées avec quantité et cohérentes avec l'intitulé de la tâche.", "kind": "field_consistency", "severity": "error", "message": "Pièce de rechange incohérente avec l'intitulé de la tâche."},
    "MAT_SECTION_PRELIM": {"description": "Consignations, mises en sécurité et préparations avant les étapes principales.", "kind": "section_required", "severity": "error", "message": "Section « Tâches préliminaires » absente."},
    "MAT_SECTION_POST": {"description": "Tests fonctionnels, déconsignation et remise en configuration vol.", "kind": "section_required", "severity": "error", "message": "Section « Tâches post-maintenance » absente."},
    "MAT_STEP_VERB": {"description": "Chaque étape numérotée doit commencer par un verbe à l'infinitif.", "kind": "step_pattern", "severity": "warning", "message": "Étape : verbe à l'infinitif requis."},
    "MAT_REF_FORMAT": {"description": "Les renvois vers une autre tâche MAT10000 doivent suivre le format MAT-XX-YY-ZZ-NNN.", "kind": "regex_flag", "severity": "info", "message": "Référence MAT10000 — vérifier le format MAT-XX-YY-ZZ-NNN."},
    "MAT_NO_PASSIVE": {"description": "Les étapes doivent être à l'impératif actif.", "kind": "regex_flag", "severity": "warning", "message": "Voix passive — réécrire à l'impératif actif."},
    "MAT_TERMINOLOGY_DANGER": {"description": "Préférer DANGER / WARNING / CAUTION à Attention / Important.", "kind": "term_replace", "severity": "warning", "replacement": "CAUTION", "message": "Préférer DANGER / WARNING / CAUTION (hiérarchie MAT10000)."},
    "MAT_TORQUE_UNIT": {"description": "Les couples de serrage sont exprimés en N·m.", "kind": "regex_flag", "severity": "info", "message": "Couple en unités impériales — convertir en N·m."},
}

_ENGLISH_RULE_METADATA: dict[str, tuple[str, str]] = {
    "MAT_FIELD_PERIODICITE": (
        "For every preventive maintenance task, the periodicity must be explicitly specified.",
        "Periodicity field required for preventive maintenance.",
    ),
    "MAT_FIELD_DUREE": (
        "The estimated procedure duration must be specified for maintenance planning.",
        "Duration field missing.",
    ),
    "MAT_FIELD_PERSONNEL": (
        "The required number and qualification of operators must be specified.",
        "Required personnel field missing.",
    ),
    "MAT_FIELD_NIVEAU": (
        "Maintenance level NTI-1 / NTI-2 / NTI-3, or Line / Base / Shop.",
        "Maintenance level missing or outside the enumeration.",
    ),
    "MAT_SECTION_EQUIPEMENT": (
        "Section listing the required tooling and support equipment.",
        "Support equipment section missing.",
    ),
    "MAT_SECTION_CONSOMMABLES": (
        "List of consumables required by the task.",
        "Consumables section missing.",
    ),
    "MAT_SECTION_RECHANGE": (
        "Spare parts listed with quantity and consistent with the task title.",
        "Spare part is inconsistent with the task title.",
    ),
    "MAT_SECTION_PRELIM": (
        "Lockout, safety, and preparation before the main procedure steps.",
        "Preliminary tasks section missing.",
    ),
    "MAT_SECTION_POST": (
        "Functional tests, lockout removal, and return to flight configuration.",
        "Post-maintenance tasks section missing.",
    ),
    "MAT_STEP_VERB": (
        "Every numbered step must start with an infinitive verb.",
        "Step: an infinitive verb is required.",
    ),
    "MAT_REF_FORMAT": (
        "References to another MAT10000 task must follow the MAT-XX-YY-ZZ-NNN format.",
        "MAT10000 reference - check the MAT-XX-YY-ZZ-NNN format.",
    ),
    "MAT_NO_PASSIVE": (
        "Steps must use the active imperative form.",
        "Passive voice - rewrite in the active imperative.",
    ),
    "MAT_TERMINOLOGY_DANGER": (
        "Prefer DANGER / WARNING / CAUTION to Attention / Important.",
        "Prefer DANGER / WARNING / CAUTION according to the MAT10000 hierarchy.",
    ),
    "MAT_TORQUE_UNIT": (
        "Torque values must be expressed in N.m.",
        "Torque in imperial units - convert to N.m.",
    ),
}

for _rule_code, (_description_en, _message_en) in _ENGLISH_RULE_METADATA.items():
    RULE_METADATA[_rule_code].update(
        description_en=_description_en,
        message_en=_message_en,
    )


CATALOG: dict[str, list[CompiledRule]] = {"v1": _RULES_V1}
