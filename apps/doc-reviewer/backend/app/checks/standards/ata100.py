"""ATA 100 revision 38 catalog, expressed with the existing CompiledRule contract."""

from __future__ import annotations

from app.core.compiled_rules import Check, CompiledRule, RuleTarget


_TARGET = RuleTarget(page="all", region="full_page")
_ORIGIN = "ATA100:rev 38"


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


_RULES_REV38 = [
    _rule(
        "ATA_CHAPTER_REF",
        "Référence chapitre ATA mal formée",
        r"\b(?i:ATA|Chapter|Chapitre)\s+(?!\d{2}-\d{2}-\d{2}\b)\d{1,3}(?:\s*[-./]\s*\d{1,3}){0,2}\b",
    ),
    _rule(
        "ATA_CHAPTER_RANGE",
        "Chapitre ATA dans l'intervalle 0-99",
        r"\bCh(?:apter|apitre)\s+(?:[1-9]\d{2,}|0?[a-zA-Z])",
    ),
    _rule(
        "ATA_FIELD_EFFECTIVITY",
        "Effectivité (Effectivity) renseignée",
        r"(?is)^(?!.*\b(?:Effectivity|Effectivité|Applicability)\b).*$",
    ),
    _rule(
        "ATA_FIELD_PERIODICITE",
        "Périodicité (preventive)",
        r"(?is)^(?=.*\b(?:preventive|scheduled|periodic|programmée|programmee|préventive)\b)(?!.*\b(?:Interval|Periodicity|Périodicité|Frequency)\b).*$",
    ),
    _rule(
        "ATA_FIELD_DUREE",
        "Durée de la procédure",
        r"(?is)^(?!.*\b(?:Duration|Elapsed time|Durée|Man-hours)\b).*$",
    ),
    _rule(
        "ATA_FIELD_PERSONNEL",
        "Personnel (manpower) listé",
        r"(?is)^(?!.*\b(?:Manpower|Personnel|Crew|Skill level)\b).*$",
    ),
    _rule(
        "ATA_FIELD_NIVEAU",
        "Niveau de maintenance",
        r"(?is)^(?!.*\bMaintenance\s+level\s*[:=]\s*(?:Line|Base|Shop)\b).*$",
    ),
    _rule(
        "ATA_SECTION_TOOLS",
        "Tools and equipment listés",
        r"(?is)^(?!.*\b(?:Tools and equipment|Outillage|Tooling)\b).*$",
    ),
    _rule(
        "ATA_SECTION_CONSUMABLES",
        "Consumables listés",
        r"(?is)^(?!.*\b(?:Consumables|Consommables|Materials)\b).*$",
    ),
    _rule(
        "ATA_SECTION_SPARES",
        "Spare parts cohérents avec la tâche",
        r"(?is)^(?=.*\b(?:replace|remove|install|remplacer|déposer|installer)\b)(?!.*\b(?:part|assembly|module|pièce|piece|ensemble)\b).*$",
    ),
    _rule(
        "ATA_SECTION_PRELIM",
        "Preliminary procedure / safety",
        r"(?is)^(?!.*\b(?:Preliminary|Safety precautions|Tâches préliminaires|Consignation)\b).*$",
    ),
    _rule(
        "ATA_SECTION_CLOSE",
        "Close out / post-maintenance",
        r"(?is)^(?!.*\b(?:Close out|Restoration|Post-maintenance|Functional test)\b).*$",
    ),
    _rule(
        "ATA_STEP_VERB",
        "Étape commençant par un verbe à l'infinitif",
        r"(?im)^\s*(?:(?:Step|Étape|Etape)\s+)?\(?\d+[.)\]]\s+(?!(?:Remove|Inspect|Verify|Install|Replace|Disconnect|Connect|Open|Close|Check|Clean|Measure|Adjust|Set|Record|Ensure|Retirer|Inspecter|Vérifier|Installer|Remplacer|Déposer|Déconnecter|Connecter|Ouvrir|Fermer|Contrôler|Nettoyer|Mesurer|Régler|Noter)\b|[A-ZÀ-Ÿ][a-zà-ÿ]+(?:er|ir|re|oir)\b).+",
    ),
    _rule(
        "ATA_NO_AMBIGUOUS_QUANT",
        "Quantificateurs ambigus à éviter",
        r"(?i)\b(?:some|a few|several|plusieurs)\b",
    ),
    _rule(
        "ATA_TORQUE_DUAL_UNIT",
        "Couple en unité duale (N·m + lb·ft)",
        r"(?is)^(?=.*\btorque\b)(?!.*(?:\b\d+(?:\.\d+)?\s*N[·.]?m\b.*\b\d+(?:\.\d+)?\s*lb[·.]?ft\b|\b\d+(?:\.\d+)?\s*lb[·.]?ft\b.*\b\d+(?:\.\d+)?\s*N[·.]?m\b)).*$",
    ),
]


RULE_METADATA = {
    "ATA_CHAPTER_REF": {"description": "Signale les références explicitement préfixées ATA, Chapter ou Chapitre qui ne suivent pas le format chapitre-section-sujet (ex : ATA 24-21-00).", "kind": "regex_flag", "severity": "warning", "message": "Référence ATA mal formée — utiliser le format CH-SE-SU."},
    "ATA_CHAPTER_RANGE": {"description": "Le chapitre principal ATA 100 est numéroté de 00 (général) à 99. Toute valeur hors plage est invalide.", "kind": "regex_flag", "severity": "error", "message": "Chapitre ATA hors plage 00-99."},
    "ATA_FIELD_EFFECTIVITY": {"description": "Toute procédure doit déclarer son effectivité (série/configuration applicable).", "kind": "field_required", "severity": "warning", "message": "Champ « Effectivity » manquant."},
    "ATA_FIELD_PERIODICITE": {"description": "Pour les tâches de maintenance programmée, la fréquence (FH / FC / CAL) doit être indiquée.", "kind": "field_required", "severity": "warning", "message": "Champ « Périodicité » manquant pour une tâche programmée.", "metadata": {"conditional": "task_type=preventive"}},
    "ATA_FIELD_DUREE": {"description": "Elapsed time / man-hours requis pour le planning.", "kind": "field_required", "severity": "info", "message": "Champ « Durée » manquant."},
    "ATA_FIELD_PERSONNEL": {"description": "Nombre et qualification des techniciens requis.", "kind": "field_required", "severity": "info", "message": "Champ « Personnel » manquant."},
    "ATA_FIELD_NIVEAU": {"description": "Line / Base / Shop selon l'environnement d'exécution prévu.", "kind": "enum_value", "severity": "warning", "message": "Niveau de maintenance manquant ou hors énumération.", "metadata": {"field_label": "Maintenance level"}},
    "ATA_SECTION_TOOLS": {"description": "Section listant l'outillage requis (P/N, source) — obligatoire dans toute procédure ATA.", "kind": "section_required", "severity": "warning", "message": "Section « Tools and equipment » absente."},
    "ATA_SECTION_CONSUMABLES": {"description": "Huiles, graisses, joints, frein-filets…", "kind": "section_required", "severity": "warning", "message": "Section « Consumables » absente."},
    "ATA_SECTION_SPARES": {"description": "Cohérence entre l'intitulé (REPLACE / REMOVE / INSTALL) et la liste de rechange.", "kind": "field_consistency", "severity": "error", "message": "Spare parts incohérents avec l'intitulé de la tâche."},
    "ATA_SECTION_PRELIM": {"description": "Section de mise en sécurité avant les étapes principales.", "kind": "section_required", "severity": "error", "message": "Section « Preliminary / Safety » absente."},
    "ATA_SECTION_CLOSE": {"description": "Section de remise en configuration vol et tests fonctionnels en fin de procédure.", "kind": "section_required", "severity": "error", "message": "Section « Close out / post-maintenance » absente."},
    "ATA_STEP_VERB": {"description": "Chaque étape numérotée doit commencer par un verbe d'action à l'impératif/infinitif.", "kind": "step_pattern", "severity": "warning", "message": "Étape : verbe à l'infinitif requis."},
    "ATA_NO_AMBIGUOUS_QUANT": {"description": "Éviter « some », « a few », « several » — préférer une quantité chiffrée.", "kind": "regex_flag", "severity": "info", "message": "Quantificateur ambigu — préférer une valeur chiffrée."},
    "ATA_TORQUE_DUAL_UNIT": {"description": "Les valeurs de couple doivent être présentées dans les deux unités (SI primaire, impérial secondaire).", "kind": "regex_flag", "severity": "info", "message": "Couple — vérifier la présence des deux unités (N·m / lb·ft)."},
}

_ENGLISH_RULE_METADATA: dict[str, tuple[str, str]] = {
    "ATA_CHAPTER_REF": (
        "Flags references explicitly prefixed ATA, Chapter, or Chapitre that do not follow the chapter-section-subject format (for example, ATA 24-21-00).",
        "Malformed ATA reference - use the CH-SE-SU format.",
    ),
    "ATA_CHAPTER_RANGE": (
        "The main ATA 100 chapter is numbered from 00 (general) to 99. Any value outside this range is invalid.",
        "ATA chapter outside the 00-99 range.",
    ),
    "ATA_FIELD_EFFECTIVITY": (
        "Every procedure must declare its effectivity (applicable series/configuration).",
        "Effectivity field missing.",
    ),
    "ATA_FIELD_PERIODICITE": (
        "For scheduled maintenance tasks, the frequency (FH / FC / CAL) must be specified.",
        "Periodicity field missing for a scheduled task.",
    ),
    "ATA_FIELD_DUREE": (
        "Elapsed time / man-hours are required for planning.",
        "Duration field missing.",
    ),
    "ATA_FIELD_PERSONNEL": (
        "The required number and qualification of technicians must be specified.",
        "Personnel field missing.",
    ),
    "ATA_FIELD_NIVEAU": (
        "Line / Base / Shop according to the planned execution environment.",
        "Maintenance level missing or outside the enumeration.",
    ),
    "ATA_SECTION_TOOLS": (
        "Section listing the required tooling (P/N, source), mandatory in every ATA procedure.",
        "Tools and equipment section missing.",
    ),
    "ATA_SECTION_CONSUMABLES": (
        "Oils, greases, seals, thread lockers, and other consumables required by the procedure.",
        "Consumables section missing.",
    ),
    "ATA_SECTION_SPARES": (
        "Consistency between the task title (REPLACE / REMOVE / INSTALL) and the spare-parts list.",
        "Spare parts are inconsistent with the task title.",
    ),
    "ATA_SECTION_PRELIM": (
        "Safety section before the main procedure steps.",
        "Preliminary / Safety section missing.",
    ),
    "ATA_SECTION_CLOSE": (
        "Section for returning to flight configuration and performing functional tests at the end of the procedure.",
        "Close-out / post-maintenance section missing.",
    ),
    "ATA_STEP_VERB": (
        "Every numbered step must start with an action verb in the imperative or infinitive form.",
        "Step: an infinitive verb is required.",
    ),
    "ATA_NO_AMBIGUOUS_QUANT": (
        "Avoid 'some', 'a few', and 'several'; use a numbered quantity instead.",
        "Ambiguous quantifier - use a numbered value.",
    ),
    "ATA_TORQUE_DUAL_UNIT": (
        "Torque values must be presented in both units (primary SI, secondary imperial).",
        "Torque - check that both units (N.m / lb.ft) are present.",
    ),
}

for _rule_code, (_description_en, _message_en) in _ENGLISH_RULE_METADATA.items():
    RULE_METADATA[_rule_code].update(
        description_en=_description_en,
        message_en=_message_en,
    )


CATALOG: dict[str, list[CompiledRule]] = {"rev 38": _RULES_REV38}
