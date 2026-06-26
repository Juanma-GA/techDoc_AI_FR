"""Règles métier Corpus Agent v4 — défauts en dur + override persistant.

- `load_rules()` retourne le contenu de `data/rules.json` s'il existe,
  mergé avec `DEFAULT_RULES` pour les clés absentes ; sinon `DEFAULT_RULES`.
- `save_rules(rules)` écrit `data/rules.json` (UI Paramètres).
- `reset_rules()` supprime le fichier → revient aux défauts du code.

`DEFAULT_RULES` encode le référentiel de contrôle v4. Chaque clé de premier
niveau correspond à une famille de règles consommée par le module de check
homonyme dans `app/checks/`. Les valeurs sont soit des paramètres
(préfixes, colonnes, seuils), soit des phrases standardisées de référence.

Familles → type(s) d'anomalie émis :
  script          → "script"
  granule         → "granule"
  texte_general   → "texte", "ordre_taches", "tache_induite", "orthographe"
  rechanges       → "rechange"
  outillages      → "outillage"
  infrastructure  → "infrastructure"
  entete_recap    → "entete"
  mise_en_securite→ "securite"
  preliminaires   → "preliminaire"
  valeurs_num     → "valeur_numerique"
  serrage         → "serrage"
  complementaires → "complementaire"
  illustrations   → "illustration"
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Optional

from app.config import settings


# `storage_dir` est `…/data/storage`, donc on remonte d'un cran pour
# placer rules.json à côté de la DB SQLite (`…/data/rules.json`).
_RULES_FILE = Path(settings.storage_dir).parent / "rules.json"


# Liste des types d'anomalie émis par le moteur v4. Sert de source de vérité
# pour les agrégats KPI (api/kpis.py) et les filtres de l'UI React.
ANOMALY_TYPES: list[str] = [
    "script",
    "granule",
    "texte",
    "ordre_taches",
    "tache_induite",
    "orthographe",
    "rechange",
    "outillage",
    "infrastructure",
    "entete",
    "securite",
    "preliminaire",
    "valeur_numerique",
    "serrage",
    "complementaire",
    "illustration",
    "personnalisee",
]


DEFAULT_RULES: dict[str, Any] = {
    # ====================================================================
    # SCRIPT & GRANULE
    # ====================================================================
    # Le script de la FTM doit commencer par "DMC-TG5-" suivi d'un code
    # (AAAA) et être identique au script de référence du suivi ATM FTM,
    # colonne BF.
    "script": {
        "prefixe": "DMC-TG5-",
        # AAAA = 4 caractères alphanumériques après le préfixe.
        "regex": r"^DMC-TG5-[A-Z0-9]{4}",
        "atm_colonne": "BF",  # colonne Excel du suivi ATM = script de référence
    },
    # Granule(s) à reporter depuis le suivi ATM :
    #  - opération hors dépose-pose : 1 granule, colonne BH ;
    #  - opération de dépose-pose : 2 granules — la dépose (ligne 3.1) prend
    #    la colonne BH, la pose (ligne 3.2) prend la colonne BJ.
    "granule": {
        "atm_colonne_defaut": "BH",      # opération simple + dépose (ligne 3.1)
        "atm_colonne_pose": "BJ",        # pose (ligne 3.2) des opérations dépose-pose
        "ligne_depose": "3.1",
        "ligne_pose": "3.2",
    },

    # ====================================================================
    # GÉNÉRAL — texte des opérations
    # ====================================================================
    "texte_general": {
        # Pas d'espace en début de phrase / de cellule.
        "pas_espace_debut": True,
        # Un point ('.') doit clore chaque fin d'opération.
        "point_fin_operation": True,
        # Une phrase doit commencer soit par un verbe d'action, soit par
        # "Si" (associé à "alors"), soit par "Note".
        "debuts_autorises": ["verbe_action", "si_alors", "note"],
        # Colonne "Ordre des tâches" : aucune cellule vide, aucun saut de
        # numéro, aucun doublon.
        "colonne_ordre_taches": "Ordre des tâches",
        # Quand une tâche est appelée, sa référence doit figurer dans la
        # colonne "Tâche induite".
        "colonne_tache_induite": "Tâche induite",
        # Vérifier orthographe, grammaire et traduction (jugé par Mistral).
        "verifier_orthographe_grammaire": True,
    },

    # ====================================================================
    # RECHANGES
    # ====================================================================
    "rechanges": {
        # Le nom du rechange doit être identique à celui du LCC / de la BASL.
        "nom_identique_basl": True,
        # Une ligne = un seul rechange.
        "un_rechange_par_ligne": True,
        # Aucun doublon dans les lignes de rechanges.
        "interdire_doublons": True,
        # Tout rechange du "Récapitulatif" doit être présent sur l'onglet
        # "Tâche de maintenance".
        "recap_present_sur_tache": True,
    },

    # ====================================================================
    # OUTILLAGES
    # ====================================================================
    "outillages": {
        # Outillage standard : référence = 1, 2, 3, 4… (incrémentée),
        # désignation identique à la BASL.
        "standard_reference_incrementale": True,
        "standard_designation_basl": True,
        # Outillage spécifique : référence ET désignation reprises de la BASL.
        "specifique_reference_basl": True,
        "specifique_designation_basl": True,
        # Tout outillage du "Récapitulatif" doit être présent sur "Tâche de
        # maintenance" — sauf l'exception ci-dessous (outillage standard).
        "recap_present_sur_tache": True,
        "exceptions_recap": ["CAISSE A OUTILS STANDARD"],
    },

    # ====================================================================
    # INFRASTRUCTURE
    # ====================================================================
    "infrastructure": {
        # Référence et désignation reprises de la BASL.
        "reference_designation_basl": True,
        # Les infrastructures sont citées uniquement sur le "Récapitulatif".
        "seulement_sur_recapitulatif": True,
    },

    # ====================================================================
    # EN-TÊTE DU RÉCAPITULATIF
    # ====================================================================
    # Ces champs de l'en-tête doivent être identiques à ceux de la BASL.
    "entete_recap": {
        "champs_identiques_basl": [
            "ALC",
            "LCN",
            "Id_tâche",
            "désignation",
            "Période tâche",
            "Réf_période tâche",
        ],
    },

    # ====================================================================
    # OPÉRATIONS DE MISE EN SÉCURITÉ (standardisées)
    # ====================================================================
    "mise_en_securite": {
        "operations_standard": [
            "Appliquer impérativement les procédures de sécurité en vigueur "
            "sur le lieu de l'intervention.",
            "Immobiliser la rame.",
            "S'assurer de porter les EPI adaptés afin de se prémunir des risques xx.",
        ],
    },

    # ====================================================================
    # OPÉRATIONS PRÉLIMINAIRES
    # ====================================================================
    "preliminaires": {
        # Si aucune opération préliminaire n'est nécessaire : "Non applicable.".
        "mention_si_vide": "Non applicable.",
        # Phrases standardisées attendues selon le contexte de l'intervention.
        "hors_tension": "Consigner électriquement la rame.",
        "sans_pression_air": "Isoler pneumatiquement la rame.",
        "avant_operation_sensible": "Préparer la rame.",
        # Si l'équipement n'est pas accessible, ajouter des opérations
        # d'accessibilité aux préliminaires.
        "accessibilite_si_non_accessible": True,
    },

    # ====================================================================
    # VALEURS NUMÉRIQUES
    # ====================================================================
    "valeurs_num": {
        # Toute valeur numérique doit être accompagnée de son unité.
        "unite_obligatoire": True,
        # Un intervalle de tolérance doit suivre le format
        # [Mesure inférieure ; Mesure supérieure].
        "format_intervalle": "[inf ; sup]",
        "regex_intervalle": r"\[\s*[^;\]]+\s*;\s*[^;\]]+\s*\]",
    },

    # ====================================================================
    # SERRAGE
    # ====================================================================
    "serrage": {
        # Tout couple de serrage impose un marquage à l'écrimétal.
        "phrase_type": "Serrer au couple de XX N.m, avec marquage à l'écrimétal.",
        "marquage_ecrimetal_obligatoire": True,
        # Le couple doit être une valeur fixe — aucune tolérance admise.
        "couple_valeur_fixe": True,
        # Ne jamais resserrer une vis dévissée : rebuter l'ensemble de
        # fixation complet et le remplacer par un neuf.
        "rebuter_fixation_devissee": True,
    },

    # ====================================================================
    # OPÉRATIONS COMPLÉMENTAIRES
    # ====================================================================
    "complementaires": {
        # Si aucune opération complémentaire : "Non applicable.".
        "mention_si_vide": "Non applicable.",
        # Contre-actions attendues si l'opération préliminaire correspondante
        # a été réalisée (clé préliminaire → phrase complémentaire).
        "contre_actions": {
            "Consigner électriquement la rame.": "Déconsigner électriquement la rame.",
            "Isoler pneumatiquement la rame.": "Déconsigner pneumatiquement la rame.",
            "Préparer la rame.": "Dépréparer la rame.",
        },
        # Pour la majorité des procédures de remplacement et de pose/dépose,
        # un test de l'équipement doit figurer dans les complémentaires.
        "test_equipement_attendu": True,
    },

    # ====================================================================
    # ILLUSTRATIONS
    # ====================================================================
    "illustrations": {
        # Tout repérage de figure suit la forme RepXX(FigZZ).
        "format_reperage": "RepXX(FigZZ)",
        "regex_reperage": r"Rep\d+\(Fig\d+\)",
        # Tous les repères appelés dans le texte doivent être visibles sur
        # les images, et tous les repères visibles doivent être appelés.
        "coherence_reperes": True,
        # Largeur des illustrations : entre 900 et 1200 pixels.
        "largeur_min_px": 900,
        "largeur_max_px": 1200,
        # Taille totale des illustrations : 400 Ko maximum.
        "taille_totale_max_ko": 400,
        # Règles de conformité visuelle évaluées par le modèle vision Mistral
        # sur chaque illustration (EPI, pictogrammes, lisibilité…). Liste vide
        # = pas de contrôle visuel. Skippé si Mistral non configuré.
        "conformite_visuelle": [
            "Si une personne est visible, porte-t-elle les EPI adaptés "
            "(casque, gants, lunettes, chaussures de sécurité) ?",
            "Si l'opération illustrée présente un risque, un pictogramme de "
            "sécurité ou un panneau d'avertissement est-il visible ?",
            "L'illustration est-elle nette, lisible et en couleur "
            "(pas un scan noir et blanc dégradé) ?",
            "L'illustration est-elle exempte de marque commerciale ou de logo "
            "de fournisseur identifiable ?",
            "Si l'image comporte des flèches ou repères numérotés, leur "
            "numérotation et leur orientation sont-elles cohérentes ?",
            "Si l'image comporte des repères numérotés, pointent-ils bien sur "
            "les articles associés (vis, rondelles, contacteur, etc.) — pas sur "
            "des éléments adjacents ou non concernés ?",
        ],
    },

    # ====================================================================
    # RÈGLES PERSONNALISÉES (évaluées par l'IA embarquée)
    # ====================================================================
    # Règles définies dynamiquement par l'utilisateur dans l'onglet Paramètres.
    # Chaque règle : {id, label, consigne (langage naturel), severity}.
    # Le check `custom_rules` les soumet à Mistral à chaque analyse → anomalies
    # de type `personnalisee`. Liste vide = aucune règle IA.
    "regles_personnalisees": [],

    # Consignes libres ajoutées aux prompts Mistral (orthographe, jugements).
    "instructions_libres": "",
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Fusion récursive : pour chaque clé, si les deux valeurs sont des
    dicts on descend ; sinon l'override remplace le défaut. Les listes
    ne sont pas mergées (l'override remplace entièrement la liste) pour
    laisser le rédacteur contrôler explicitement les listes (ex. règles
    personnalisées, opérations standard)."""
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_rules() -> dict[str, Any]:
    """Lecture des règles : override `data/rules.json` mergé en profondeur
    avec les défauts. Si le fichier est absent ou invalide → défauts.

    Le merge est récursif sur les dicts : une famille (ex. `illustrations`)
    peut être partiellement sauvegardée — les clés absentes (ex.
    `conformite_visuelle`) sont complétées par les défauts du code, ce qui
    évite de désactiver silencieusement des contrôles après une sauvegarde
    UI qui n'aurait pas exposé toutes les clés.
    """
    defaults = copy.deepcopy(DEFAULT_RULES)
    if _RULES_FILE.exists():
        try:
            data = json.loads(_RULES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return _deep_merge(defaults, data)
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


# Colonnes de référence « builtin » : noms réservés, consommés par les checks
# `script` / `granule`. Non supprimables ni renommables côté UI.
BUILTIN_COLUMN_NAMES: tuple[str, ...] = ("script", "granule_defaut", "granule_pose")


def _builtin_defaults() -> list[dict[str, Any]]:
    """Défauts des 3 colonnes builtin : lettres depuis `rules.json`, onglet
    vide (= recherche par mots-clés, compat. ascendante)."""
    rules = load_rules()
    return [
        {"name": "script", "sheet": "",
         "column": str((rules.get("script") or {}).get("atm_colonne") or "BF"),
         "builtin": True},
        {"name": "granule_defaut", "sheet": "",
         "column": str((rules.get("granule") or {}).get("atm_colonne_defaut") or "BH"),
         "builtin": True},
        {"name": "granule_pose", "sheet": "",
         "column": str((rules.get("granule") or {}).get("atm_colonne_pose") or "BJ"),
         "builtin": True},
    ]


def reference_columns_for(project: Any) -> list[dict[str, Any]]:
    """Registre des colonnes de référence d'un projet.

    Lit `project.reference_columns` (liste JSON `{name,sheet,column,builtin}`,
    définie via le mapping du référentiel). Garantit toujours la présence des
    3 colonnes builtin — mergées avec le stockage, défauts `rules.json` sinon.
    Les colonnes non-builtin de l'utilisateur suivent.
    """
    defaults = _builtin_defaults()
    raw = getattr(project, "reference_columns", None)
    stored: list[Any] = []
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                stored = parsed
        except (json.JSONDecodeError, TypeError):
            stored = []

    by_name: dict[str, dict[str, Any]] = {}
    for entry in stored:
        if isinstance(entry, dict) and entry.get("name"):
            by_name[str(entry["name"])] = entry

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for d in defaults:
        e = by_name.get(d["name"])
        if e:
            out.append({
                "name": d["name"],
                "sheet": str(e.get("sheet") or ""),
                "column": str(e.get("column") or d["column"]),
                "builtin": True,
            })
        else:
            out.append(dict(d))
        seen.add(d["name"])

    for entry in stored:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append({
            "name": name,
            "sheet": str(entry.get("sheet") or ""),
            "column": str(entry.get("column") or ""),
            "builtin": False,
        })
    return out


def reference_column(project: Any, name: str) -> Optional[dict[str, Any]]:
    """Colonne de référence d'un projet par son nom (None si introuvable)."""
    for col in reference_columns_for(project):
        if col["name"] == name:
            return col
    return None


# Colonnes BASL « builtin » : noms réservés, consommés par le check
# `referentiel_items` (cross-check rechanges / outillages / infrastructure).
# Non supprimables ni renommables côté UI. Onglet/colonne vides par défaut =
# repli sur l'union de toutes les cellules de la BASL (compat. ascendante).
BASL_BUILTIN_COLUMN_NAMES: tuple[str, ...] = ("rechange", "outillage", "infrastructure")


def basl_columns_for(project: Any) -> list[dict[str, Any]]:
    """Registre des colonnes BASL d'un projet — miroir de
    `reference_columns_for`, mais lit `project.basl_columns`.

    Garantit toujours la présence des 3 colonnes builtin (rechange, outillage,
    infrastructure), mergées avec le stockage. Les colonnes builtin ont un
    onglet/colonne vide par défaut : tant qu'elles ne sont pas mappées, le
    check retombe sur l'union de toutes les cellules de la BASL.
    """
    defaults = [
        {"name": n, "sheet": "", "column": "", "builtin": True}
        for n in BASL_BUILTIN_COLUMN_NAMES
    ]
    raw = getattr(project, "basl_columns", None)
    stored: list[Any] = []
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                stored = parsed
        except (json.JSONDecodeError, TypeError):
            stored = []

    by_name: dict[str, dict[str, Any]] = {}
    for entry in stored:
        if isinstance(entry, dict) and entry.get("name"):
            by_name[str(entry["name"])] = entry

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for d in defaults:
        e = by_name.get(d["name"])
        if e:
            out.append({
                "name": d["name"],
                "sheet": str(e.get("sheet") or ""),
                "column": str(e.get("column") or ""),
                "builtin": True,
            })
        else:
            out.append(dict(d))
        seen.add(d["name"])

    for entry in stored:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append({
            "name": name,
            "sheet": str(entry.get("sheet") or ""),
            "column": str(entry.get("column") or ""),
            "builtin": False,
        })
    return out


def basl_column(project: Any, name: str) -> Optional[dict[str, Any]]:
    """Colonne BASL d'un projet par son nom (None si introuvable)."""
    for col in basl_columns_for(project):
        if col["name"] == name:
            return col
    return None


def save_rules(rules: dict[str, Any]) -> None:
    """Écrit le dict de règles dans `data/rules.json`."""
    _RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RULES_FILE.write_text(
        json.dumps(rules, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def reset_rules() -> None:
    """Supprime le fichier override → revient aux défauts du code."""
    if _RULES_FILE.exists():
        _RULES_FILE.unlink()


def is_overridden() -> bool:
    return _RULES_FILE.exists()
