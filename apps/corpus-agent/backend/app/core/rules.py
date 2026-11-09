"""Règles Corpus Agent — store des règles personnalisées (checklist) + helpers.

corpus-agent n'évalue plus que via la checklist : les règles déterministes
codées ont été retirées. Ce module ne conserve donc que :

- le store `regles_personnalisees` / `instructions_libres` (persisté dans
  `data/rules.json`, alimenté par l'import checklist et l'édition Paramètres,
  consommé par `checks/custom_rules.py`) ;
- les registres de colonnes de référence / BASL d'un projet, utilisés par les
  placeholders `{nom}` des consignes custom et par l'onglet mapping référentiel.

- `load_rules()` retourne le contenu de `data/rules.json` s'il existe, mergé
  avec `DEFAULT_RULES` pour les clés absentes ; sinon `DEFAULT_RULES`.
- `save_rules(rules)` écrit `data/rules.json`.
- `reset_rules()` supprime le fichier → revient aux défauts du code.

The demo checklist uses `rules.demo.json`; normal checklist operations never
read or modify that file, and demo operations never modify `rules.json`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.demo_mode import get_demo_enabled
from app.db.models import AppConfig
from app.db.session import SessionLocal

# `storage_dir` est `…/data/storage`, donc on remonte d'un cran pour
# placer rules.json à côté de la DB SQLite (`…/data/rules.json`).
_RULES_FILE = Path(settings.storage_dir).parent / "rules.json"
_DEMO_CHECKLIST_VERSION_KEY = "demo_checklist_version"
_DEMO_CHECKLIST_VERSION = "1"


def _rules_file() -> Path:
    with SessionLocal() as db:
        demo = get_demo_enabled(db)
    return _RULES_FILE.with_name("rules.demo.json") if demo else _RULES_FILE


# Liste des types d'anomalie émis par le moteur. Sert de source de vérité pour
# les agrégats KPI (api/kpis.py) et les filtres de l'UI React.
ANOMALY_TYPES: list[str] = [
    "reference_cross_check",
    "personnalisee",
]


DEFAULT_RULES: dict[str, Any] = {
    # ====================================================================
    # RÈGLES PERSONNALISÉES (évaluées par l'IA embarquée) — SEULE SOURCE
    # ====================================================================
    # Règles de la checklist : importées en masse (import Excel) ou saisies
    # dans l'onglet Paramètres. Chaque règle : {id, label, consigne (langage
    # naturel), severity, validated}. Le check `custom_rules` les soumet à
    # Mistral à chaque analyse → anomalies de type `personnalisee`. Liste vide
    # = aucune règle → aucune anomalie.
    "regles_personnalisees": [],

    # Consignes libres ajoutées aux prompts Mistral (contexte de jugement).
    "instructions_libres": "",
}


DEMO_CHECKLIST: list[dict[str, Any]] = [
    {
        "id": "demo-safety",
        "label": "Sécurité des interventions",
        "consigne": (
            "Pour chaque intervention présentant un risque, vérifier que les étapes "
            "préalables de sécurité et de mise en sécurité des énergies sont explicites."
        ),
        "severity": "high",
        "validated": True,
        "enabled": True,
    },
    {
        "id": "demo-tooling",
        "label": "Outillage et calibration",
        "consigne": (
            "Vérifier que l'outillage nécessaire est identifié par référence et que "
            "les exigences de calibration applicables sont précisées."
        ),
        "severity": "medium",
        "validated": True,
        "enabled": True,
    },
    {
        "id": "demo-parts",
        "label": "Pièces et consommables",
        "consigne": (
            "Vérifier que les pièces et consommables indiquent une référence, une "
            "quantité, une unité et une condition de remplacement compréhensibles."
        ),
        "severity": "medium",
        "validated": True,
        "enabled": True,
    },
    {
        "id": "demo-qualification",
        "label": "Qualification requise",
        "consigne": (
            "Vérifier que la qualification requise est indiquée pour chaque tâche "
            "et cohérente avec l'intervention décrite."
        ),
        "severity": "medium",
        "validated": True,
        "enabled": True,
    },
    {
        "id": "demo-revision-history",
        "label": "Traçabilité des révisions",
        "consigne": (
            "Vérifier que chaque révision comporte une date, un auteur et une "
            "description suffisamment claire de la modification."
        ),
        "severity": "low",
        "validated": True,
        "enabled": True,
    },
]


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
    rules_file = _rules_file()
    if rules_file.exists():
        try:
            data = json.loads(rules_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return _deep_merge(defaults, data)
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def ensure_demo_checklist(db: Session) -> None:
    """Initialize the demo checklist once without replacing an existing one."""
    if not get_demo_enabled(db):
        return

    marker = db.get(AppConfig, _DEMO_CHECKLIST_VERSION_KEY)
    if marker is not None and marker.value == _DEMO_CHECKLIST_VERSION:
        return

    rules = load_rules()
    if not rules.get("regles_personnalisees"):
        rules["regles_personnalisees"] = copy.deepcopy(DEMO_CHECKLIST)
        save_rules(rules)

    if marker is None:
        db.add(AppConfig(key=_DEMO_CHECKLIST_VERSION_KEY, value=_DEMO_CHECKLIST_VERSION))
    else:
        marker.value = _DEMO_CHECKLIST_VERSION
    db.commit()


# Colonnes de référence « builtin » : noms réservés, consommés par les checks
# `script` / `granule`. Non supprimables ni renommables côté UI.
BUILTIN_COLUMN_NAMES: tuple[str, ...] = ("script", "granule_defaut", "granule_pose")


def _builtin_defaults() -> list[dict[str, Any]]:
    """Défauts des 3 colonnes de référence builtin (lettres ATM classiques,
    onglet vide = recherche par mots-clés, compat. ascendante). Ces colonnes
    restent exposées à l'onglet mapping référentiel et adressables depuis les
    consignes custom via les placeholders `{script}` / `{granule_defaut}` /
    `{granule_pose}`."""
    return [
        {"name": "script", "sheet": "", "column": "BF", "builtin": True},
        {"name": "granule_defaut", "sheet": "", "column": "BH", "builtin": True},
        {"name": "granule_pose", "sheet": "", "column": "BJ", "builtin": True},
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


# Colonnes BASL « builtin » : noms réservés (rechange / outillage /
# infrastructure), exposés par l'onglet mapping référentiel et adressables
# depuis les consignes custom. Non supprimables ni renommables côté UI.
# Onglet/colonne vides par défaut.
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
    """Write rules to the current mode's isolated checklist."""
    rules_file = _rules_file()
    rules_file.parent.mkdir(parents=True, exist_ok=True)
    rules_file.write_text(
        json.dumps(rules, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def reset_rules() -> None:
    """Supprime le fichier override → revient aux défauts du code."""
    rules_file = _rules_file()
    if rules_file.exists():
        rules_file.unlink()


def is_overridden() -> bool:
    return _rules_file().exists()
