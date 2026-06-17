"""Etapes 3 & 4 - lecture / edition du SMGXML (format texte de CATComposer).

Le SMGXML porte les acteurs (pieces) affiches dans l'ecosysteme moteur. Ce
module sait :
  - **recolor** (etape 3) : poser une couleur RGB sur les acteurs dont le nom
    correspond a un SIN / CATPart mono-couleur.
  - **rename** (etape 4) : remplacer le nom d'une ancienne piece par la nouvelle
    (attribut de nom ET references) partout dans le fichier.

Posture : **dry-run par defaut** (on calcule les changements sans ecrire).
Quand `apply=True`, on ecrit le fichier en conservant une copie `.bak`.

Les noms d'attributs exacts du SMGXML varient selon la version Composer ->
`NAME_ATTRS` / `COLOR_ATTR` / `COLOR_FORMAT` sont ajustables (TODO : confirmer
sur un SMGXML reel).
"""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from typing import Callable, Optional

from app.core.errors import AppError


# Attributs portant le nom d'un acteur / piece (TODO : confirmer Composer).
NAME_ATTRS: tuple[str, ...] = ("name", "Name", "actorName", "title", "label", "id", "Id")
# Attribut couleur (TODO : confirmer Composer).
COLOR_ATTR: str = "color"


def _local(tag: str) -> str:
    """Tag sans namespace ('{ns}Actor' -> 'Actor')."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def color_to_str(rgb: tuple[int, int, int]) -> str:
    """Representation couleur ecrite dans le SMGXML. TODO : confirmer le format
    attendu par Composer (ici 'r,g,b' en 0-255)."""
    return f"{rgb[0]},{rgb[1]},{rgb[2]}"


def _name_of(elem: ET.Element) -> Optional[str]:
    for attr in NAME_ATTRS:
        v = elem.get(attr)
        if v:
            return v
    return None


def parse_actors(path: str, limit: int = 5000) -> list[dict]:
    """Liste les acteurs (elements portant un attribut de nom) pour inspection."""
    root = _parse(path)
    out: list[dict] = []
    for elem in root.iter():
        name = _name_of(elem)
        if not name:
            continue
        out.append({"name": name, "tag": _local(elem.tag), "color": elem.get(COLOR_ATTR, "")})
        if len(out) >= limit:
            break
    return out


def _parse(path: str) -> ET.Element:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as e:
        raise AppError("SMGXML_INVALID", f"SMGXML illisible (XML invalide) : {e}", status_code=400) from e
    except OSError as e:
        raise AppError("SMGXML_NOT_FOUND", "SMGXML introuvable ou illisible.", status_code=400) from e


def _recolor(root: ET.Element, color_map: dict[str, tuple[int, int, int]], fmt: Callable) -> list[dict]:
    changes: list[dict] = []
    for elem in root.iter():
        name = _name_of(elem)
        if not name or name not in color_map:
            continue
        old = elem.get(COLOR_ATTR, "")
        new = fmt(color_map[name])
        if old == new:
            continue
        elem.set(COLOR_ATTR, new)
        changes.append({"target": name, "change_type": "color", "old_value": old, "new_value": new})
    return changes


def _rename(root: ET.Element, rename_map: dict[str, str]) -> list[dict]:
    changes: list[dict] = []
    for elem in root.iter():
        for attr, value in list(elem.attrib.items()):
            if value in rename_map:
                new = rename_map[value]
                elem.set(attr, new)
                changes.append(
                    {"target": _local(elem.tag), "change_type": "rename", "old_value": value, "new_value": new}
                )
    return changes


def process(
    path: str,
    operation: str,
    *,
    color_map: Optional[dict[str, tuple[int, int, int]]] = None,
    rename_map: Optional[dict[str, str]] = None,
    apply: bool = False,
    output_path: Optional[str] = None,
) -> dict:
    """Calcule (et applique si `apply`) les changements sur le SMGXML.

    Retour : {changes, applied, backup_path, output_path, summary}.
    En mode `apply` in-place, une copie `.bak` de l'original est conservee.
    """
    tree = ET.ElementTree(_parse(path))
    root = tree.getroot()

    if operation == "recolor":
        changes = _recolor(root, color_map or {}, color_to_str)
    elif operation == "rename":
        changes = _rename(root, rename_map or {})
    else:
        raise AppError("SMGXML_OP_INVALID", "operation attendue : recolor ou rename.", status_code=400)

    backup_path = ""
    written = ""
    if apply and changes:
        out = output_path or path
        if out == path:
            backup_path = path + ".bak"
            shutil.copy2(path, backup_path)
        tree.write(out, encoding="utf-8", xml_declaration=True)
        written = out

    summary = {
        "operation": operation,
        "changes": len(changes),
        "applied": bool(written),
    }
    return {
        "changes": changes,
        "applied": bool(written),
        "backup_path": backup_path,
        "output_path": written,
        "summary": summary,
    }
