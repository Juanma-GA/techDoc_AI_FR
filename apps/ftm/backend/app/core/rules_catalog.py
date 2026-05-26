"""Catalogue déclaratif des règles métier FTM Agent.

CE FICHIER EST LA SOURCE DE VÉRITÉ pour les règles appliquées par le moteur.
Il est volontairement long (~700 lignes, dépasse la limite POC de 200) parce
que c'est un DOCUMENT DE SPECIFICATION, pas du code métier. La consigne du
projet : « UI Paramètres en lecture seule, modifications côté script » →
toute évolution d'une règle se fait ICI, dans une seule passe.

Lecture conseillée : suivre l'ordre des sections (matche la spec métier des
experts FTM). Chaque règle suit le même format :

    NOM_REGLE = register(Rule(
        id              : identifiant stable (jamais renommé)
        family          : groupement UI (script, illustrations, …)
        severity        : low / medium / high
        anomaly_types   : type(s) d'anomalie émis
        requires        : capabilités runtime requises (vide = déterministe)
        enabled_default : True / False par défaut
        params          : paramètres de la règle (clé Excel, regex, etc.)
        examples        : cas valides / invalides pour la doc UI
        legacy_resolver : lecture depuis rules.json legacy (read)
        legacy_keys     : écriture vers rules.json legacy (write)
        legacy_enabled_key : si le legacy a une clé booléenne native pour
                             le toggle on/off de cette règle
    ))

Les modules `app/checks/*.py` importent leurs règles depuis ici via :

    from app.core.rules_catalog import SCRIPT_FORMAT, GRANULE_REPORT, ...

et accèdent au runtime via `resolve_rules()[SCRIPT_FORMAT.id]`.
"""

from __future__ import annotations

from typing import Any

from app.core.rules_registry import Example, ParamSchema, Rule, register


# ----------------------------------------------------------------------------
# Helpers de lecture du `rules.json` legacy (lambdas legacy_resolver).
# ----------------------------------------------------------------------------

def _L(legacy: dict, family: str, key: str, default: Any = None) -> Any:
    """Lit `legacy[family][key]` avec fallback `default` si absent ou mal typé."""
    fam = legacy.get(family)
    if not isinstance(fam, dict):
        return default
    val = fam.get(key)
    return val if val is not None else default


# Défauts de listes/maps utilisés à plusieurs endroits.
_DEFAULT_OPS_SECURITE = [
    "Appliquer impérativement les procédures de sécurité en vigueur sur le lieu de l'intervention.",
    "Immobiliser la rame.",
    "S'assurer de porter les EPI adaptés afin de se prémunir des risques xx.",
]
_DEFAULT_CONTRE_ACTIONS = {
    "Consigner électriquement la rame.": "Déconsigner électriquement la rame.",
    "Isoler pneumatiquement la rame.": "Déconsigner pneumatiquement la rame.",
    "Préparer la rame.": "Dépréparer la rame.",
}
_DEFAULT_ENTETE_BASL = [
    "ALC", "LCN", "Id_tâche", "désignation", "Période tâche", "Réf_période tâche",
]
_DEFAULT_VISION_QUESTIONS = [
    "Si une personne est visible, porte-t-elle les EPI adaptés (casque, gants, lunettes, chaussures de sécurité) ?",
    "Si l'opération illustrée présente un risque, un pictogramme de sécurité ou un panneau d'avertissement est-il visible ?",
    "L'illustration est-elle nette, lisible et en couleur (pas un scan noir et blanc dégradé) ?",
    "L'illustration est-elle exempte de marque commerciale ou de logo de fournisseur identifiable ?",
    "Si l'image comporte des flèches ou repères numérotés, leur numérotation et leur orientation sont-elles cohérentes ?",
    "Si l'image comporte des repères numérotés, pointent-ils bien sur les articles associés (vis, rondelles, contacteur, etc.) — pas sur des éléments adjacents ou non concernés ?",
]


# ============================================================================
# 1. SCRIPT & GRANULE
# ============================================================================

# Le script de la FTM doit commencer par DMC-TG5-AAAA et correspondre au script
# du suivi ATM FTM (colonne BF du référentiel projet).
SCRIPT_FORMAT = register(Rule(
    id="script.format",
    family="script",
    name_key="rules.script.format.name",
    description_key="rules.script.format.description",
    severity="high",
    anomaly_types=("script",),
    enabled_default=True,
    params={
        "prefix": ParamSchema(type="string", default="DMC-TG5-",
                              name_key="rules.script.format.prefix"),
        "regex": ParamSchema(type="regex", default=r"^DMC-TG5-[A-Z0-9]{4}",
                             name_key="rules.script.format.regex"),
        "atm_colonne": ParamSchema(type="string", default="BF",
                                   name_key="rules.script.format.atm_colonne"),
    },
    examples=(
        Example("DMC-TG5-A1B2", valid=True),
        Example("DMC-TG-1234", valid=False, note_key="examples.script.bad_prefix"),
        Example("DMC-TG5-XX", valid=False, note_key="examples.script.too_short"),
    ),
    legacy_resolver=lambda L: (True, {
        "prefix": _L(L, "script", "prefixe", "DMC-TG5-"),
        "regex": _L(L, "script", "regex", r"^DMC-TG5-[A-Z0-9]{4}"),
        "atm_colonne": _L(L, "script", "atm_colonne", "BF"),
    }),
    legacy_keys={"prefix": "prefixe", "regex": "regex", "atm_colonne": "atm_colonne"},
))

# Hors dépose-pose : 1 granule colonne BH du suivi ATM.
# Dépose-pose : ligne 3.1 prend BH (dépose), ligne 3.2 prend BJ (pose).
GRANULE_REPORT = register(Rule(
    id="granule.report",
    family="granule",
    name_key="rules.granule.report.name",
    description_key="rules.granule.report.description",
    severity="high",
    anomaly_types=("granule",),
    enabled_default=True,
    params={
        "atm_colonne_defaut": ParamSchema(type="string", default="BH",
                                          name_key="rules.granule.report.atm_colonne_defaut"),
        "atm_colonne_pose": ParamSchema(type="string", default="BJ",
                                        name_key="rules.granule.report.atm_colonne_pose"),
        "ligne_depose": ParamSchema(type="string", default="3.1",
                                    name_key="rules.granule.report.ligne_depose"),
        "ligne_pose": ParamSchema(type="string", default="3.2",
                                  name_key="rules.granule.report.ligne_pose"),
    },
    legacy_resolver=lambda L: (True, {
        "atm_colonne_defaut": _L(L, "granule", "atm_colonne_defaut", "BH"),
        "atm_colonne_pose": _L(L, "granule", "atm_colonne_pose", "BJ"),
        "ligne_depose": _L(L, "granule", "ligne_depose", "3.1"),
        "ligne_pose": _L(L, "granule", "ligne_pose", "3.2"),
    }),
    legacy_keys={
        "atm_colonne_defaut": "atm_colonne_defaut",
        "atm_colonne_pose": "atm_colonne_pose",
        "ligne_depose": "ligne_depose",
        "ligne_pose": "ligne_pose",
    },
))


# ============================================================================
# 2. GÉNÉRAL — Texte & structure
# ============================================================================

# Format des phrases : pas d'espace en début, point final, début autorisé
# (verbe d'action / Si...alors / Note).
TEXTE_FORMAT_PHRASE = register(Rule(
    id="texte.format_phrase",
    family="texte_general",
    name_key="rules.texte.format_phrase.name",
    description_key="rules.texte.format_phrase.description",
    severity="medium",
    anomaly_types=("texte",),
    enabled_default=True,
    params={
        "pas_espace_debut": ParamSchema(type="bool", default=True,
                                        name_key="rules.texte.format_phrase.pas_espace_debut"),
        "point_fin_operation": ParamSchema(type="bool", default=True,
                                           name_key="rules.texte.format_phrase.point_fin_operation"),
        "debuts_autorises": ParamSchema(type="list[str]",
                                        default=["verbe_action", "si_alors", "note"],
                                        name_key="rules.texte.format_phrase.debuts_autorises"),
    },
    legacy_resolver=lambda L: (True, {
        "pas_espace_debut": bool(_L(L, "texte_general", "pas_espace_debut", True)),
        "point_fin_operation": bool(_L(L, "texte_general", "point_fin_operation", True)),
        "debuts_autorises": list(_L(L, "texte_general", "debuts_autorises",
                                    ["verbe_action", "si_alors", "note"])),
    }),
    legacy_keys={
        "pas_espace_debut": "pas_espace_debut",
        "point_fin_operation": "point_fin_operation",
        "debuts_autorises": "debuts_autorises",
    },
))

# La colonne « Ordre des tâches » : pas de cellule vide, pas de saut, pas de doublon.
TEXTE_ORDRE_TACHES = register(Rule(
    id="texte.ordre_taches",
    family="texte_general",
    name_key="rules.texte.ordre_taches.name",
    description_key="rules.texte.ordre_taches.description",
    severity="high",
    anomaly_types=("ordre_taches",),
    enabled_default=True,
    params={
        "colonne": ParamSchema(type="string", default="Ordre des tâches",
                               name_key="rules.texte.ordre_taches.colonne"),
    },
    legacy_resolver=lambda L: (True, {
        "colonne": str(_L(L, "texte_general", "colonne_ordre_taches", "Ordre des tâches")),
    }),
    legacy_keys={"colonne": "colonne_ordre_taches"},
))

# Toute tâche appelée doit avoir sa référence en colonne « Tâche induite ».
TEXTE_TACHE_INDUITE = register(Rule(
    id="texte.tache_induite",
    family="texte_general",
    name_key="rules.texte.tache_induite.name",
    description_key="rules.texte.tache_induite.description",
    severity="medium",
    anomaly_types=("tache_induite",),
    enabled_default=True,
    params={
        "colonne": ParamSchema(type="string", default="Tâche induite",
                               name_key="rules.texte.tache_induite.colonne"),
    },
    legacy_resolver=lambda L: (True, {
        "colonne": str(_L(L, "texte_general", "colonne_tache_induite", "Tâche induite")),
    }),
    legacy_keys={"colonne": "colonne_tache_induite"},
))

# Si le titre du livrable est « remplacer », alors l'ordre des tâches doit
# comporter une ligne 3.1 « déposer » et une ligne 3.2 « poser ».
TEXTE_REMPLACER_DEPOSE_POSE = register(Rule(
    id="texte.remplacer_depose_pose",
    family="texte_general",
    name_key="rules.texte.remplacer_depose_pose.name",
    description_key="rules.texte.remplacer_depose_pose.description",
    severity="high",
    anomaly_types=("ordre_taches",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (True, {}),
))

# Vérification orthographe / grammaire / traduction via Mistral.
TEXTE_ORTHOGRAPHE = register(Rule(
    id="texte.orthographe",
    family="texte_general",
    name_key="rules.texte.orthographe.name",
    description_key="rules.texte.orthographe.description",
    severity="low",
    anomaly_types=("orthographe",),
    requires=("mistral_chat",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (
        bool(_L(L, "texte_general", "verifier_orthographe_grammaire", True)), {}),
    legacy_enabled_key="verifier_orthographe_grammaire",
))


# ============================================================================
# 3. RECHANGES
# ============================================================================

# Le nom du rechange doit être identique à celui du LCC / de la BASL.
RECHANGES_NOM_BASL = register(Rule(
    id="rechanges.nom_basl",
    family="rechanges",
    name_key="rules.rechanges.nom_basl.name",
    description_key="rules.rechanges.nom_basl.description",
    severity="medium",
    anomaly_types=("rechange",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (bool(_L(L, "rechanges", "nom_identique_basl", True)), {}),
    legacy_enabled_key="nom_identique_basl",
))

# Une ligne = un seul rechange + aucun doublon.
RECHANGES_DOUBLONS = register(Rule(
    id="rechanges.doublons",
    family="rechanges",
    name_key="rules.rechanges.doublons.name",
    description_key="rules.rechanges.doublons.description",
    severity="medium",
    anomaly_types=("rechange",),
    enabled_default=True,
    params={
        "un_par_ligne": ParamSchema(type="bool", default=True,
                                    name_key="rules.rechanges.doublons.un_par_ligne"),
    },
    legacy_resolver=lambda L: (
        bool(_L(L, "rechanges", "interdire_doublons", True)),
        {"un_par_ligne": bool(_L(L, "rechanges", "un_rechange_par_ligne", True))},
    ),
    legacy_enabled_key="interdire_doublons",
    legacy_keys={"un_par_ligne": "un_rechange_par_ligne"},
))

# Tout rechange du Récapitulatif doit être présent sur la Tâche de maintenance.
RECHANGES_RECAP_PRESENT = register(Rule(
    id="rechanges.recap_present",
    family="rechanges",
    name_key="rules.rechanges.recap_present.name",
    description_key="rules.rechanges.recap_present.description",
    severity="medium",
    anomaly_types=("rechange",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (bool(_L(L, "rechanges", "recap_present_sur_tache", True)), {}),
    legacy_enabled_key="recap_present_sur_tache",
))


# ============================================================================
# 4. OUTILLAGES
# ============================================================================

# Outillage standard : référence incrémentale (col AW à incrémenter 1,2,3…)
# + désignation identique à la BASL.
OUTILLAGES_STANDARD = register(Rule(
    id="outillages.standard",
    family="outillages",
    name_key="rules.outillages.standard.name",
    description_key="rules.outillages.standard.description",
    severity="low",
    anomaly_types=("outillage",),
    enabled_default=True,
    params={
        "reference_incrementale": ParamSchema(type="bool", default=True,
                                              name_key="rules.outillages.standard.reference_incrementale"),
        "designation_basl": ParamSchema(type="bool", default=True,
                                        name_key="rules.outillages.standard.designation_basl"),
    },
    legacy_resolver=lambda L: (True, {
        "reference_incrementale": bool(_L(L, "outillages", "standard_reference_incrementale", True)),
        "designation_basl": bool(_L(L, "outillages", "standard_designation_basl", True)),
    }),
    legacy_keys={
        "reference_incrementale": "standard_reference_incrementale",
        "designation_basl": "standard_designation_basl",
    },
))

# Outillage spécifique : référence ET désignation reprises de la BASL.
OUTILLAGES_SPECIFIQUE = register(Rule(
    id="outillages.specifique",
    family="outillages",
    name_key="rules.outillages.specifique.name",
    description_key="rules.outillages.specifique.description",
    severity="medium",
    anomaly_types=("outillage",),
    enabled_default=True,
    params={
        "reference_basl": ParamSchema(type="bool", default=True,
                                      name_key="rules.outillages.specifique.reference_basl"),
        "designation_basl": ParamSchema(type="bool", default=True,
                                        name_key="rules.outillages.specifique.designation_basl"),
    },
    legacy_resolver=lambda L: (True, {
        "reference_basl": bool(_L(L, "outillages", "specifique_reference_basl", True)),
        "designation_basl": bool(_L(L, "outillages", "specifique_designation_basl", True)),
    }),
    legacy_keys={
        "reference_basl": "specifique_reference_basl",
        "designation_basl": "specifique_designation_basl",
    },
))

# Tout outillage du Récap doit être présent sur Tâche de maintenance — sauf
# « CAISSE A OUTILS STANDARD » (et autres exceptions configurées).
OUTILLAGES_RECAP_PRESENT = register(Rule(
    id="outillages.recap_present",
    family="outillages",
    name_key="rules.outillages.recap_present.name",
    description_key="rules.outillages.recap_present.description",
    severity="medium",
    anomaly_types=("outillage",),
    enabled_default=True,
    params={
        "exceptions": ParamSchema(type="list[str]", default=["CAISSE A OUTILS STANDARD"],
                                  name_key="rules.outillages.recap_present.exceptions"),
    },
    legacy_resolver=lambda L: (
        bool(_L(L, "outillages", "recap_present_sur_tache", True)),
        {"exceptions": list(_L(L, "outillages", "exceptions_recap", ["CAISSE A OUTILS STANDARD"]))},
    ),
    legacy_enabled_key="recap_present_sur_tache",
    legacy_keys={"exceptions": "exceptions_recap"},
))


# ============================================================================
# 5. LUBRIFIANT
# ============================================================================

# Si « lubrifiant » est mentionné dans le texte, sa référence doit être
# renseignée dans la colonne dédiée. SPEC INCOMPLÈTE : colonne à confirmer
# avec l'équipe métier → désactivée par défaut.
LUBRIFIANT_REFERENCE = register(Rule(
    id="lubrifiant.reference",
    family="lubrifiant",
    name_key="rules.lubrifiant.reference.name",
    description_key="rules.lubrifiant.reference.description",
    severity="low",
    anomaly_types=("outillage",),
    enabled_default=False,
    params={},
    legacy_resolver=lambda L: (False, {}),
))


# ============================================================================
# 6. INFRASTRUCTURE
# ============================================================================

# Référence + désignation reprises de la BASL ; infrastructures citées
# uniquement sur le Récapitulatif (pas sur la Tâche de maintenance).
INFRASTRUCTURE_BASL = register(Rule(
    id="infrastructure.basl",
    family="infrastructure",
    name_key="rules.infrastructure.basl.name",
    description_key="rules.infrastructure.basl.description",
    severity="medium",
    anomaly_types=("infrastructure",),
    enabled_default=True,
    params={
        "seulement_recap": ParamSchema(type="bool", default=True,
                                       name_key="rules.infrastructure.basl.seulement_recap"),
    },
    legacy_resolver=lambda L: (
        bool(_L(L, "infrastructure", "reference_designation_basl", True)),
        {"seulement_recap": bool(_L(L, "infrastructure", "seulement_sur_recapitulatif", True))},
    ),
    legacy_enabled_key="reference_designation_basl",
    legacy_keys={"seulement_recap": "seulement_sur_recapitulatif"},
))


# ============================================================================
# 7. EN-TÊTE DU RÉCAPITULATIF
# ============================================================================

# ALC, LCN, Id_tâche, désignation, Période tâche, Réf_période tâche doivent
# être identiques à ceux de la BASL.
ENTETE_RECAP_CHAMPS = register(Rule(
    id="entete_recap.champs",
    family="entete_recap",
    name_key="rules.entete_recap.champs.name",
    description_key="rules.entete_recap.champs.description",
    severity="medium",
    anomaly_types=("entete",),
    enabled_default=True,
    params={
        "champs_identiques_basl": ParamSchema(
            type="list[str]", default=_DEFAULT_ENTETE_BASL,
            name_key="rules.entete_recap.champs.champs_identiques_basl",
        ),
    },
    legacy_resolver=lambda L: (True, {
        "champs_identiques_basl": list(_L(L, "entete_recap", "champs_identiques_basl",
                                          _DEFAULT_ENTETE_BASL)),
    }),
    legacy_keys={"champs_identiques_basl": "champs_identiques_basl"},
))


# ============================================================================
# 8. OPÉRATIONS DE MISE EN SÉCURITÉ
# ============================================================================

# Liste des phrases standardisées (procédures de sécurité, EPI, immobilisation).
SECURITE_OPS_STD = register(Rule(
    id="securite.operations_standard",
    family="mise_en_securite",
    name_key="rules.securite.operations_standard.name",
    description_key="rules.securite.operations_standard.description",
    severity="medium",
    anomaly_types=("securite",),
    enabled_default=True,
    params={
        "operations": ParamSchema(type="list[str]", default=_DEFAULT_OPS_SECURITE,
                                  name_key="rules.securite.operations_standard.operations"),
    },
    legacy_resolver=lambda L: (True, {
        "operations": list(_L(L, "mise_en_securite", "operations_standard", _DEFAULT_OPS_SECURITE)),
    }),
    legacy_keys={"operations": "operations_standard"},
))


# ============================================================================
# 9. OPÉRATIONS PRÉLIMINAIRES
# ============================================================================

# Phrases standardisées (hors tension, sans pression d'air, avant opération
# sensible, mention si vide, accessibilité).
PRELIMINAIRES_PHRASES = register(Rule(
    id="preliminaires.phrases",
    family="preliminaires",
    name_key="rules.preliminaires.phrases.name",
    description_key="rules.preliminaires.phrases.description",
    severity="high",
    anomaly_types=("preliminaire",),
    enabled_default=True,
    params={
        "mention_si_vide": ParamSchema(type="string", default="Non applicable.",
                                       name_key="rules.preliminaires.phrases.mention_si_vide"),
        "hors_tension": ParamSchema(type="string",
                                    default="Consigner électriquement la rame.",
                                    name_key="rules.preliminaires.phrases.hors_tension"),
        "sans_pression_air": ParamSchema(type="string",
                                         default="Isoler pneumatiquement la rame.",
                                         name_key="rules.preliminaires.phrases.sans_pression_air"),
        "avant_operation_sensible": ParamSchema(type="string",
                                                default="Préparer la rame.",
                                                name_key="rules.preliminaires.phrases.avant_operation_sensible"),
        "accessibilite_si_non_accessible": ParamSchema(type="bool", default=True,
                                                       name_key="rules.preliminaires.phrases.accessibilite_si_non_accessible"),
    },
    legacy_resolver=lambda L: (True, {
        "mention_si_vide": str(_L(L, "preliminaires", "mention_si_vide", "Non applicable.")),
        "hors_tension": str(_L(L, "preliminaires", "hors_tension", "Consigner électriquement la rame.")),
        "sans_pression_air": str(_L(L, "preliminaires", "sans_pression_air", "Isoler pneumatiquement la rame.")),
        "avant_operation_sensible": str(_L(L, "preliminaires", "avant_operation_sensible", "Préparer la rame.")),
        "accessibilite_si_non_accessible": bool(_L(L, "preliminaires", "accessibilite_si_non_accessible", True)),
    }),
    legacy_keys={
        "mention_si_vide": "mention_si_vide",
        "hors_tension": "hors_tension",
        "sans_pression_air": "sans_pression_air",
        "avant_operation_sensible": "avant_operation_sensible",
        "accessibilite_si_non_accessible": "accessibilite_si_non_accessible",
    },
))

# Disjoncteur coupé en préliminaire → doit être enclenché en complémentaire.
PRELIMINAIRES_DISJONCTEUR = register(Rule(
    id="preliminaires.disjoncteur",
    family="preliminaires",
    name_key="rules.preliminaires.disjoncteur.name",
    description_key="rules.preliminaires.disjoncteur.description",
    severity="high",
    anomaly_types=("complementaire",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (True, {}),
))


# ============================================================================
# 10. VALEURS NUMÉRIQUES
# ============================================================================

# Toute valeur numérique décimale doit être accompagnée d'une unité (mm, N.m, V, …).
VALEURS_UNITE_OBLIGATOIRE = register(Rule(
    id="valeurs_num.unite_obligatoire",
    family="valeurs_num",
    name_key="rules.valeurs_num.unite_obligatoire.name",
    description_key="rules.valeurs_num.unite_obligatoire.description",
    severity="medium",
    anomaly_types=("valeur_numerique",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (bool(_L(L, "valeurs_num", "unite_obligatoire", True)), {}),
    legacy_enabled_key="unite_obligatoire",
))

# Format des intervalles de tolérance : [Mesure inférieure ; Mesure supérieure].
VALEURS_FORMAT_INTERVALLE = register(Rule(
    id="valeurs_num.format_intervalle",
    family="valeurs_num",
    name_key="rules.valeurs_num.format_intervalle.name",
    description_key="rules.valeurs_num.format_intervalle.description",
    severity="medium",
    anomaly_types=("valeur_numerique",),
    enabled_default=True,
    params={
        "format": ParamSchema(type="string", default="[inf ; sup]",
                              name_key="rules.valeurs_num.format_intervalle.format"),
    },
    legacy_resolver=lambda L: (True, {
        "format": str(_L(L, "valeurs_num", "format_intervalle", "[inf ; sup]")),
    }),
    legacy_keys={"format": "format_intervalle"},
))


# ============================================================================
# 11. SERRAGE
# ============================================================================

# Couple de serrage mentionné → marquage à l'écrimétal obligatoire.
SERRAGE_ECRIMETAL = register(Rule(
    id="serrage.marquage_ecrimetal",
    family="serrage",
    name_key="rules.serrage.marquage_ecrimetal.name",
    description_key="rules.serrage.marquage_ecrimetal.description",
    severity="high",
    anomaly_types=("serrage",),
    enabled_default=True,
    params={
        "phrase_type": ParamSchema(
            type="string",
            default="Serrer au couple de XX N.m, avec marquage à l'écrimétal.",
            name_key="rules.serrage.marquage_ecrimetal.phrase_type",
        ),
    },
    legacy_resolver=lambda L: (
        bool(_L(L, "serrage", "marquage_ecrimetal_obligatoire", True)),
        {"phrase_type": str(_L(L, "serrage", "phrase_type",
                               "Serrer au couple de XX N.m, avec marquage à l'écrimétal."))},
    ),
    legacy_enabled_key="marquage_ecrimetal_obligatoire",
    legacy_keys={"phrase_type": "phrase_type"},
))

# Couple de serrage = valeur fixe (pas de tolérance ± ni « entre X et Y »).
SERRAGE_COUPLE_FIXE = register(Rule(
    id="serrage.couple_fixe",
    family="serrage",
    name_key="rules.serrage.couple_fixe.name",
    description_key="rules.serrage.couple_fixe.description",
    severity="high",
    anomaly_types=("serrage",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (bool(_L(L, "serrage", "couple_valeur_fixe", True)), {}),
    legacy_enabled_key="couple_valeur_fixe",
))

# Une vis dévissée est rebutée : ne jamais resserrer, remplacer la fixation complète.
SERRAGE_REBUTER_DEVISSEE = register(Rule(
    id="serrage.rebuter_devissee",
    family="serrage",
    name_key="rules.serrage.rebuter_devissee.name",
    description_key="rules.serrage.rebuter_devissee.description",
    severity="medium",
    anomaly_types=("serrage",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (bool(_L(L, "serrage", "rebuter_fixation_devissee", True)), {}),
    legacy_enabled_key="rebuter_fixation_devissee",
))

# Lorsque les termes serrage/serrer sont mentionnés, un couple doit être renseigné.
SERRAGE_COUPLE_SI_SERRAGE = register(Rule(
    id="serrage.couple_si_serrage",
    family="serrage",
    name_key="rules.serrage.couple_si_serrage.name",
    description_key="rules.serrage.couple_si_serrage.description",
    severity="medium",
    anomaly_types=("serrage",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (True, {}),
))

# Goupille de verrouillage : le serrage au couple n'est PAS recommandé.
SERRAGE_GOUPILLE_VERROUILLAGE = register(Rule(
    id="serrage.goupille_verrouillage",
    family="serrage",
    name_key="rules.serrage.goupille_verrouillage.name",
    description_key="rules.serrage.goupille_verrouillage.description",
    severity="low",
    anomaly_types=("serrage",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (True, {}),
))

# Couple de serrage → outillage de mesure spécifié en colonne AY du FTM.
SERRAGE_OUTILLAGE_AY = register(Rule(
    id="serrage.outillage_ay",
    family="serrage",
    name_key="rules.serrage.outillage_ay.name",
    description_key="rules.serrage.outillage_ay.description",
    severity="medium",
    anomaly_types=("serrage",),
    enabled_default=True,
    params={
        "colonne": ParamSchema(type="string", default="AY",
                               name_key="rules.serrage.outillage_ay.colonne"),
    },
    legacy_resolver=lambda L: (True, {"colonne": "AY"}),
    legacy_keys={"colonne": "outillage_couple_colonne"},
))


# ============================================================================
# 12. FIXER
# ============================================================================

# Lorsque fixer/visser sont mentionnés, des visseries (vis, rondelle, écrou)
# doivent figurer dans les colonnes BB et BD du FTM.
FIXER_VISSERIES = register(Rule(
    id="fixer.visseries",
    family="fixer",
    name_key="rules.fixer.visseries.name",
    description_key="rules.fixer.visseries.description",
    severity="medium",
    anomaly_types=("outillage",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (True, {}),
))

# BB et BD doivent contenir le même nombre d'articles par ligne.
FIXER_MEME_NOMBRE = register(Rule(
    id="fixer.meme_nombre",
    family="fixer",
    name_key="rules.fixer.meme_nombre.name",
    description_key="rules.fixer.meme_nombre.description",
    severity="low",
    anomaly_types=("outillage",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (True, {}),
))


# ============================================================================
# 13. VERROUILLER
# ============================================================================

# Lorsque déverrouiller / verrouiller / verrouillant sont mentionnés, l'outil
# associé doit être indiqué en colonne AY du FTM.
VERROUILLER_OUTIL_AY = register(Rule(
    id="verrouiller.outil_ay",
    family="verrouiller",
    name_key="rules.verrouiller.outil_ay.name",
    description_key="rules.verrouiller.outil_ay.description",
    severity="medium",
    anomaly_types=("outillage",),
    enabled_default=True,
    params={
        "colonne": ParamSchema(type="string", default="AY",
                               name_key="rules.verrouiller.outil_ay.colonne"),
    },
    legacy_resolver=lambda L: (True, {"colonne": "AY"}),
    legacy_keys={"colonne": "verrouillage_outil_colonne"},
))


# ============================================================================
# 14. OPÉRATIONS COMPLÉMENTAIRES
# ============================================================================

# Si les complémentaires sont vides → « Non applicable. ». Toute préliminaire
# (consignation, isolation, préparation) doit avoir sa contre-action.
COMPLEMENTAIRES_CONTRE_ACTIONS = register(Rule(
    id="complementaires.contre_actions",
    family="complementaires",
    name_key="rules.complementaires.contre_actions.name",
    description_key="rules.complementaires.contre_actions.description",
    severity="high",
    anomaly_types=("complementaire",),
    enabled_default=True,
    params={
        "mention_si_vide": ParamSchema(type="string", default="Non applicable.",
                                       name_key="rules.complementaires.contre_actions.mention_si_vide"),
        "contre_actions": ParamSchema(type="map[str,str]", default=_DEFAULT_CONTRE_ACTIONS,
                                      name_key="rules.complementaires.contre_actions.contre_actions"),
    },
    legacy_resolver=lambda L: (True, {
        "mention_si_vide": str(_L(L, "complementaires", "mention_si_vide", "Non applicable.")),
        "contre_actions": dict(_L(L, "complementaires", "contre_actions", _DEFAULT_CONTRE_ACTIONS)),
    }),
    legacy_keys={"mention_si_vide": "mention_si_vide", "contre_actions": "contre_actions"},
))

# Pour les remplacements et pose/dépose, un test de l'équipement doit figurer
# dans les complémentaires.
COMPLEMENTAIRES_TEST_EQUIPEMENT = register(Rule(
    id="complementaires.test_equipement",
    family="complementaires",
    name_key="rules.complementaires.test_equipement.name",
    description_key="rules.complementaires.test_equipement.description",
    severity="medium",
    anomaly_types=("complementaire",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (bool(_L(L, "complementaires", "test_equipement_attendu", True)), {}),
    legacy_enabled_key="test_equipement_attendu",
))


# ============================================================================
# 15. ILLUSTRATIONS
# ============================================================================

# Format de repérage des figures : RepXX(FigZZ).
FORMAT_REPERAGE = register(Rule(
    id="illustrations.format_reperage",
    family="illustrations",
    name_key="rules.illustrations.format_reperage.name",
    description_key="rules.illustrations.format_reperage.description",
    severity="low",
    anomaly_types=("illustration",),
    enabled_default=True,
    params={
        "pattern": ParamSchema(type="regex", default=r"Rep\d+\(Fig\d+\)",
                               name_key="rules.illustrations.format_reperage.pattern"),
    },
    examples=(
        Example("Voir Rep1(Fig2) ci-dessus.", valid=True),
        Example("Rep1.(Fig2)", valid=False, note_key="examples.format_reperage.dot_parasite"),
        Example("Rep1blabla(Fig2)", valid=False, note_key="examples.format_reperage.text_between"),
    ),
    legacy_resolver=lambda L: (True, {
        "pattern": _L(L, "illustrations", "regex_reperage", r"Rep\d+\(Fig\d+\)"),
    }),
    legacy_keys={"pattern": "regex_reperage"},
))

# Largeur des illustrations : entre 900 et 1200 pixels.
DIMENSIONS = register(Rule(
    id="illustrations.dimensions",
    family="illustrations",
    name_key="rules.illustrations.dimensions.name",
    description_key="rules.illustrations.dimensions.description",
    severity="medium",
    anomaly_types=("illustration",),
    enabled_default=True,
    params={
        "min_px": ParamSchema(type="int", default=900,
                              name_key="rules.illustrations.dimensions.min_px",
                              constraints={"min": 1, "max": 10000}),
        "max_px": ParamSchema(type="int", default=1200,
                              name_key="rules.illustrations.dimensions.max_px",
                              constraints={"min": 1, "max": 10000}),
    },
    legacy_resolver=lambda L: (True, {
        "min_px": int(_L(L, "illustrations", "largeur_min_px", 900) or 900),
        "max_px": int(_L(L, "illustrations", "largeur_max_px", 1200) or 1200),
    }),
    legacy_keys={"min_px": "largeur_min_px", "max_px": "largeur_max_px"},
))

# Taille totale des illustrations : 400 Ko maximum cumulés.
TAILLE_TOTALE = register(Rule(
    id="illustrations.taille_totale",
    family="illustrations",
    name_key="rules.illustrations.taille_totale.name",
    description_key="rules.illustrations.taille_totale.description",
    severity="medium",
    anomaly_types=("illustration",),
    enabled_default=True,
    params={
        "max_ko": ParamSchema(type="int", default=400,
                              name_key="rules.illustrations.taille_totale.max_ko",
                              constraints={"min": 1, "max": 1000000}),
    },
    legacy_resolver=lambda L: (True, {
        "max_ko": int(_L(L, "illustrations", "taille_totale_max_ko", 400) or 400),
    }),
    legacy_keys={"max_ko": "taille_totale_max_ko"},
))

# Tous les repères appelés dans le texte sont visibles sur les illustrations,
# et tous les repères visibles sont appelés (croisement vision Mistral).
COHERENCE_REPERES = register(Rule(
    id="illustrations.coherence_reperes",
    family="illustrations",
    name_key="rules.illustrations.coherence_reperes.name",
    description_key="rules.illustrations.coherence_reperes.description",
    severity="high",
    anomaly_types=("illustration",),
    requires=("mistral_vision",),
    enabled_default=True,
    params={},
    legacy_resolver=lambda L: (bool(_L(L, "illustrations", "coherence_reperes", True)), {}),
    legacy_enabled_key="coherence_reperes",
))

# Questions de conformité visuelle évaluées par Mistral vision sur chaque
# illustration (EPI, pictogrammes, lisibilité, repères pointant sur les
# bons articles…).
CONFORMITE_VISUELLE = register(Rule(
    id="illustrations.conformite_visuelle",
    family="illustrations",
    name_key="rules.illustrations.conformite_visuelle.name",
    description_key="rules.illustrations.conformite_visuelle.description",
    severity="medium",
    anomaly_types=("illustration",),
    requires=("mistral_vision",),
    enabled_default=True,
    params={
        "questions": ParamSchema(type="list[str]", default=_DEFAULT_VISION_QUESTIONS,
                                 name_key="rules.illustrations.conformite_visuelle.questions"),
    },
    legacy_resolver=lambda L: (
        bool([q for q in (_L(L, "illustrations", "conformite_visuelle", _DEFAULT_VISION_QUESTIONS) or [])
              if str(q).strip()]),
        {"questions": [q for q in (_L(L, "illustrations", "conformite_visuelle",
                                      _DEFAULT_VISION_QUESTIONS) or [])
                       if str(q).strip()]},
    ),
    legacy_keys={"questions": "conformite_visuelle"},
))
