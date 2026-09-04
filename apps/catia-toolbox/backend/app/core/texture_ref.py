"""Configuration textures (etape 3) : bibliotheque de styles + extension.

Composer applique une texture a un acteur via un **nom de style** ecrit dans le
SMGXML (balise `Actor.Style` / `ActorStyle`). Ce nom pointe vers un fichier de
style de la **bibliotheque de textures** (rangee sur disque, ex. `C:\\...`), avec
l'extension `.SMGStyleSet`.

Ce module stocke la config runtime dans `app_config` (cles `texture_library` et
`style_ext`) -> pas de migration, preservee au reset admin. Il expose de quoi
formater la valeur de style ecrite dans le SMGXML : `<bibliotheque>/<nom>.<ext>`.

TODO : confirmer sur un SMGXML reel le format exact attendu par Composer
(prefixe de bibliotheque inclus ou non, separateur, casse de l'extension).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AppConfig


_KEY_LIBRARY = "texture_library"
_KEY_EXT = "style_ext"
DEFAULT_STYLE_EXT = ".SMGStyleSet"


def _get(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppConfig, key)
    return row.value if row and row.value else default


def _set(db: Session, key: str, value: str) -> None:
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=value))
    else:
        row.value = value


def get_texture_config(db: Session) -> dict:
    """Config textures : {library, ext}. `ext` par defaut `.SMGStyleSet`."""
    return {
        "library": _get(db, _KEY_LIBRARY, ""),
        "ext": _get(db, _KEY_EXT, DEFAULT_STYLE_EXT),
    }


def set_texture_config(db: Session, library: str, ext: str) -> dict:
    """Enregistre la bibliotheque de textures + l'extension de style."""
    lib = (library or "").strip()[:500]
    style_ext = (ext or "").strip()[:40] or DEFAULT_STYLE_EXT
    _set(db, _KEY_LIBRARY, lib)
    _set(db, _KEY_EXT, style_ext)
    db.commit()
    return {"library": lib, "ext": style_ext}


def format_style_value(name: str, library: str = "", ext: str = "") -> str:
    """Valeur de style ecrite dans le SMGXML : `<bibliotheque>/<nom><ext>`.

    - Ajoute l'extension (`.SMGStyleSet`) si absente (comparaison insensible a la
      casse), pour que le SMGXML pointe vers le fichier de style.
    - Prefixe par la bibliotheque de textures quand elle est configuree.
    Ne fait rien si `name` est vide.
    """
    val = (name or "").strip()
    if not val:
        return val
    if ext and not val.lower().endswith(ext.lower()):
        val = f"{val}{ext}"
    if library:
        lib = library.rstrip("/\\")
        sep = "\\" if "\\" in lib else "/"
        # Ne pas re-prefixer si le nom porte deja le chemin de la bibliotheque.
        if not val.lower().startswith(lib.lower()):
            val = f"{lib}{sep}{val}"
    return val
