"""Racines OneDrive (input / output) — detection + persistance runtime.

Approche **local-first** : OneDrive est consomme via son **dossier synchronise
local** (pas de Graph / OAuth / cloud). On ne fait que detecter et persister des
chemins de dossier ; le parcours et la lecture passent par `core/parser.py` et
`api/browse.py` (metadonnees seules).

Persistance dans la table `app_config` (key/value), meme mecanisme que la config
Mistral (`core/mistral_client.py`). Preservee par convention lors d'un reset admin.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AppConfig


INPUT_ROOT_KEY = "onedrive_input_root"
OUTPUT_ROOT_KEY = "onedrive_output_root"

# Variables d'environnement posees par le client OneDrive Windows.
_ENV_VARS = ("OneDriveCommercial", "OneDrive", "OneDriveConsumer")


def _read_config(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppConfig, key)
    return row.value if row and row.value else default


def _write_config(db: Session, key: str, value: str) -> None:
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=value))
    else:
        row.value = value


def detect_onedrive_roots() -> list[str]:
    """Renvoie les dossiers OneDrive synchronises detectes sur la machine.

    Combine les variables d'environnement OneDrive et un scan du home pour les
    dossiers commencant par "OneDrive". Ne renvoie que des chemins existants,
    dedupliques, en conservant l'ordre de decouverte.
    """
    found: list[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        if not path:
            return
        norm = os.path.normpath(path)
        if os.path.isdir(norm) and norm.lower() not in seen:
            seen.add(norm.lower())
            found.append(norm)

    for var in _ENV_VARS:
        _add(os.environ.get(var, ""))

    home = Path(os.path.expanduser("~"))
    if home.is_dir():
        try:
            for child in sorted(home.iterdir()):
                if child.is_dir() and child.name.lower().startswith("onedrive"):
                    _add(str(child))
        except OSError:
            pass

    return found


def get_onedrive_roots(db: Session) -> dict[str, str]:
    """Racines configurees (input / output). Chaine vide si non definie."""
    return {
        "input": _read_config(db, INPUT_ROOT_KEY, ""),
        "output": _read_config(db, OUTPUT_ROOT_KEY, ""),
    }


def set_onedrive_roots(
    db: Session,
    *,
    input_root: str | None = None,
    output_root: str | None = None,
) -> None:
    """Persiste les racines fournies (les valeurs None sont ignorees)."""
    changed = False
    if input_root is not None:
        _write_config(db, INPUT_ROOT_KEY, input_root.strip())
        changed = True
    if output_root is not None:
        _write_config(db, OUTPUT_ROOT_KEY, output_root.strip())
        changed = True
    if changed:
        db.commit()


def root_for_scope(db: Session, scope: str) -> str:
    """Racine configuree, ou stockage local si aucune racine n'est fournie."""
    roots = get_onedrive_roots(db)
    configured = roots.get(scope, "")
    if configured:
        return configured
    if scope in ("input", "output"):
        return settings.storage_dir
    return ""
