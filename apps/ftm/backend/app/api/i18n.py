"""GET /api/v1/i18n/{lang} — sert les traductions en JSON.

Source de vérité : `app/static/i18n/<lang>.json`.
Override utilisateur : `data/i18n/<lang>.json` (créé via UI ou Mistral plus tard).
Fallback : si la langue est absente, on retourne le contenu FR.
Ajouter une langue = déposer un fichier JSON dans `app/static/i18n/`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.config import settings
from app.core.errors import AppError


router = APIRouter(prefix="/i18n", tags=["i18n"])


_BUILTIN_DIR = Path(__file__).resolve().parent.parent / "static" / "i18n"
_OVERRIDE_DIR = Path(settings.storage_dir).parent / "i18n"
_LANG_RE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")


def _load(lang: str) -> dict[str, str]:
    if not _LANG_RE.fullmatch(lang):
        raise AppError("I18N_LANG_INVALID", f"Code langue invalide : {lang}", status_code=422)
    for path in (_OVERRIDE_DIR / f"{lang}.json", _BUILTIN_DIR / f"{lang}.json"):
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
            except (json.JSONDecodeError, OSError):
                continue
    return {}


@router.get("/{lang}")
def get_translations(lang: str) -> dict[str, Any]:
    """Retourne le dict de traductions pour `lang`.
    Si la langue est absente, retourne FR (source) avec `fallback: true`."""
    data = _load(lang)
    if not data and lang != "fr":
        return {"lang": "fr", "fallback": True, "translations": _load("fr")}
    return {"lang": lang, "fallback": False, "translations": data}


@router.get("")
def list_available_langs() -> dict[str, list[str]]:
    """Liste les langues disponibles (built-in + override)."""
    builtin = sorted(p.stem for p in _BUILTIN_DIR.glob("*.json")) if _BUILTIN_DIR.is_dir() else []
    override = sorted(p.stem for p in _OVERRIDE_DIR.glob("*.json")) if _OVERRIDE_DIR.is_dir() else []
    return {
        "builtin": builtin,
        "override": override,
        "all": sorted(set(builtin + override)),
    }
