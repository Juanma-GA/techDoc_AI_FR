"""Referentiel de couleurs : nom (ex. "Visserie") -> RGB.

Sert a l'etape 3 (colorisation SMGXML) : la colonne "Ref Couleur" de la
nomenclature porte un NOM ; ce referentiel le resout en triplet RGB ecrit dans
`Actor.Color`. Stocke dans la table `app_config` (cle `color_referential`, JSON)
-> pas de migration, preserve au reset admin comme les autres cles runtime.
"""

from __future__ import annotations

import json
import unicodedata

from sqlalchemy.orm import Session

from app.db.models import AppConfig


_KEY = "color_referential"


def norm_name(s: object) -> str:
    """Minuscule, sans accents, espaces compresses (pour l'appariement)."""
    txt = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(txt.lower().split())


def _clamp(v: object) -> int:
    try:
        return max(0, min(255, int(v)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def get_referential(db: Session) -> list[dict]:
    """Liste des entrees {name, r, g, b}. Vide si non configure."""
    row = db.get(AppConfig, _KEY)
    if not row or not row.value:
        return []
    try:
        data = json.loads(row.value)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [
        {"name": str(e.get("name", "")), "r": _clamp(e.get("r")), "g": _clamp(e.get("g")), "b": _clamp(e.get("b"))}
        for e in data
        if isinstance(e, dict) and str(e.get("name", "")).strip()
    ]


def set_referential(db: Session, entries: list[dict]) -> list[dict]:
    """Remplace le referentiel (noms vides ignores, RGB borne 0-255)."""
    clean: list[dict] = []
    seen: set[str] = set()
    for e in entries:
        name = str(e.get("name", "")).strip()[:200]
        if not name or norm_name(name) in seen:
            continue
        seen.add(norm_name(name))
        clean.append({"name": name, "r": _clamp(e.get("r")), "g": _clamp(e.get("g")), "b": _clamp(e.get("b"))})
    val = json.dumps(clean, ensure_ascii=False)
    row = db.get(AppConfig, _KEY)
    if row is None:
        db.add(AppConfig(key=_KEY, value=val))
    else:
        row.value = val
    db.commit()
    return clean


def resolve_map(db: Session) -> dict[str, tuple[int, int, int]]:
    """Map nom normalise -> (r, g, b) pour la colorisation."""
    return {norm_name(e["name"]): (e["r"], e["g"], e["b"]) for e in get_referential(db)}
