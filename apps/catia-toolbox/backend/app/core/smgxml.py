"""Etapes 3 & 4 - lecture / edition du SMGXML (format texte de CATComposer).

Le SMGXML porte les acteurs (pieces) affiches dans l'ecosysteme moteur. Ce
module sait :
  - **recolor** (etape 3) : poser sur les acteurs dont le nom correspond a une
    piece de la nomenclature :
      * un **nom de style** (`Actor.Style` @Value) tire de la colonne
        « Ref Couleur » — Composer applique ensuite la texture depuis la
        bibliotheque de styles rangee sur le disque `C:` (hors perimetre backend) ;
      * et/ou une **couleur RGB** dans `Actor.Color` (sous `SCLIT > Neutral`).
    Les deux sont configurables (`set_style` / `set_color`).
  - **rename** (etape 4) : remplacer le nom d'une ancienne piece par la nouvelle
    (attribut de nom ET references) partout dans le fichier.

Posture : **dry-run par defaut** (on calcule les changements sans ecrire).
Quand `apply=True`, on ecrit le fichier en conservant une copie `.bak`.

Les noms de balises / attributs exacts du SMGXML varient selon la version
Composer -> `NAME_ATTRS` / `STYLE_TAG` / `STYLE_VALUE_ATTR` / `COLOR_TAG` /
`COLOR_ATTR` / format couleur sont ajustables (TODO : confirmer sur un SMGXML
reel de production).
"""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from typing import Optional

from app.core.errors import AppError


# Attributs portant le nom d'un acteur / piece (TODO : confirmer Composer).
NAME_ATTRS: tuple[str, ...] = ("name", "Name", "actorName", "title", "label", "id", "Id")
# Balises portant le nom de style de texture (variantes Composer : "Actor.Style"
# @Value ou "ActorStyle"). TODO : confirmer sur un SMGXML reel.
STYLE_TAGS: tuple[str, ...] = ("Actor.Style", "ActorStyle")
STYLE_VALUE_ATTR: str = "Value"
# Balise couleur (sous SCLIT > Neutral) + attribut portant le triplet RGB.
COLOR_TAG: str = "Actor.Color"
COLOR_ATTR: str = "color"  # attribut legacy / fallback quand pas de balise dediee


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


def _build_parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    """Map enfant -> parent (ElementTree n'expose pas le parent nativement)."""
    return {child: parent for parent in root.iter() for child in parent}


def _actor_name_for(
    elem: ET.Element, parent_map: dict[ET.Element, ET.Element]
) -> Optional[str]:
    """Nom de l'acteur ancetre le plus proche portant un attribut de nom."""
    cur: Optional[ET.Element] = elem
    while cur is not None:
        name = _name_of(cur)
        if name:
            return name
        cur = parent_map.get(cur)
    return None


def _recolor(
    root: ET.Element,
    color_map: dict[str, tuple[int, int, int]],
    style_map: dict[str, str],
    *,
    set_style: bool,
    set_color: bool,
) -> list[dict]:
    """Pose le style (Actor.Style @Value) et/ou la couleur (Actor.Color) des
    acteurs dont le nom figure dans les maps.

    Deux mecanismes complementaires selon la structure reelle du fichier :
      - balises dediees `Actor.Style` / `Actor.Color` rattachees a l'acteur
        ancetre (cas Composer reel : SCLIT > Neutral > Actor.Color) ;
      - fallback : attribut `COLOR_ATTR` pose directement sur l'element nomme
        (format placeholder historique, garde pour compat / SMGXML simplifies).
    """
    parent_map = _build_parent_map(root)
    changes: list[dict] = []
    styled: set[str] = set()
    colored_via_tag: set[str] = set()

    for elem in root.iter():
        tag = _local(elem.tag)
        if set_style and tag in STYLE_TAGS:
            name = _actor_name_for(elem, parent_map)
            if name and style_map.get(name):
                old = elem.get(STYLE_VALUE_ATTR, "")
                new = style_map[name]
                styled.add(name)
                if old != new:
                    elem.set(STYLE_VALUE_ATTR, new)
                    changes.append({"target": name, "change_type": "style", "old_value": old, "new_value": new})
        elif set_color and tag == COLOR_TAG:
            name = _actor_name_for(elem, parent_map)
            if name and name in color_map:
                old = elem.get(COLOR_ATTR, "")
                new = color_to_str(color_map[name])
                colored_via_tag.add(name)
                if old != new:
                    elem.set(COLOR_ATTR, new)
                    changes.append({"target": name, "change_type": "color", "old_value": old, "new_value": new})

    # Fallback couleur : acteurs cibles sans balise Actor.Color dediee -> on
    # pose l'attribut couleur directement sur l'element nomme.
    if set_color:
        for elem in root.iter():
            name = _name_of(elem)
            if not name or name not in color_map or name in colored_via_tag:
                continue
            old = elem.get(COLOR_ATTR, "")
            new = color_to_str(color_map[name])
            if old == new:
                continue
            elem.set(COLOR_ATTR, new)
            colored_via_tag.add(name)  # une seule pose par acteur
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
    style_map: Optional[dict[str, str]] = None,
    rename_map: Optional[dict[str, str]] = None,
    set_style: bool = True,
    set_color: bool = True,
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
        changes = _recolor(
            root, color_map or {}, style_map or {}, set_style=set_style, set_color=set_color
        )
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
