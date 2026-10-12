"""Apply a Composer style-set profile to mono-body SMGXML actors."""

from __future__ import annotations

import copy
import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


STYLE_PROPERTY_NAMES = frozenset(
    {
        "Actor.Alpha",
        "Actor.Color",
        "Actor.Emission",
        "Actor.Env.Effect",
        "Actor.Env.Map.Path",
        "Actor.GeometryType",
        "Actor.Hatch.Angle",
        "Actor.Hatch.Color",
        "Actor.Hatch.Plane",
        "Actor.Hatch.Thickness",
        "Actor.LayerOpacity",
        "Actor.LinkedToolTipPropertyName",
        "Actor.Outline.Angle",
        "Actor.Outline.Color",
        "Actor.Outline.Width",
        "Actor.Shininess",
        "Texture.Activation",
        "Texture.Blending.Mode",
        "Texture.Border.Mode",
        "Texture.Image.Fill.Mode",
        "Texture.Map.Path",
        "Texture.Projection.Mode",
        "Texture.Transparency",
        "Texture.UV.Ratio",
        "Texture.UV.Scale",
    }
)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", value.casefold())


def _old_pn_pattern(value: str) -> re.Pattern[str] | None:
    normalized = _normalize(value)
    if not normalized:
        return None
    body = r"[^0-9a-z]*".join(re.escape(character) for character in normalized)
    return re.compile(rf"(?<![0-9a-z]){body}(?![0-9a-z])", re.IGNORECASE)


def _style_stem(reference: str) -> str:
    value = reference.strip()
    if not value or "/" in value or "\\" in value:
        return ""
    if value.casefold().endswith(".smgstyleset"):
        value = value[: -len(".smgStyleSet")]
    return value.strip()


def _find_child(parent: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in parent if _local_name(child.tag) == name), None)


def _same_element(left: ET.Element, right: ET.Element) -> bool:
    return left.attrib == right.attrib and left.text == right.text and len(left) == len(right)


def _copy_style(actor: ET.Element, properties: list[ET.Element], profile_name: str) -> int:
    changed = 0
    for profile_property in properties:
        property_name = _local_name(profile_property.tag)
        existing = [child for child in actor if _local_name(child.tag) == property_name]
        if len(existing) == 1 and _same_element(existing[0], profile_property):
            continue
        insert_at = list(actor).index(existing[0]) if existing else len(actor)
        for child in existing:
            actor.remove(child)
        actor.insert(insert_at, copy.deepcopy(profile_property))
        changed += 1

    style_element = _find_child(actor, "Actor.Style")
    if style_element is None:
        style_element = ET.SubElement(actor, "Actor.Style")
    if style_element.get("Value") != profile_name:
        style_element.set("Value", profile_name)
        changed += 1

    origin = actor.find("./Actor.Location/Pivot/Origin")
    path_center = _find_child(actor, "Actor.PathCenter")
    if origin is not None and path_center is None:
        path_center = ET.SubElement(actor, "Actor.PathCenter")
        for axis in ("X", "Y", "Z"):
            if axis in origin.attrib:
                path_center.set(axis, origin.get(axis, ""))
        changed += 1

    return changed


def _next_backup_path(source: Path) -> Path:
    first = Path(f"{source}.bak")
    if not first.exists():
        return first
    index = 1
    while True:
        candidate = Path(f"{source}.bak.{index}")
        if not candidate.exists():
            return candidate
        index += 1


def _write_with_backup(tree: ET.ElementTree, source: Path) -> str:
    temporary_path: Path | None = None
    backup_path = _next_backup_path(source)
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"{source.name}.", suffix=".tmp", dir=source.parent, delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        tree.write(temporary_path, encoding="utf-8", xml_declaration=True)
        shutil.copy2(source, backup_path)
        os.replace(temporary_path, source)
        return str(backup_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def colorize_mono_body_folder(
    pieces_root: Path,
    profiles_root: Path,
    mono_parts: list[dict[str, str]],
    *,
    apply: bool = False,
) -> dict:
    """Plan or apply profile styles to every matching Old P/N and geometry actor."""
    groups: dict[str, dict] = {}
    results: list[dict] = []
    for part in mono_parts:
        old_pn = str(part.get("old_pn") or "").strip()
        texture_ref = str(part.get("mono_texture") or "").strip()
        normalized_pn = _normalize(old_pn)
        if not normalized_pn:
            results.append(
                {
                    "old_pn": old_pn,
                    "texture_ref": texture_ref,
                    "path": "",
                    "status": "old_pn_missing",
                    "actors_total": 0,
                    "actors_changed": 0,
                    "backup_path": "",
                    "message": "L'OLD P/N est vide.",
                    "applied": False,
                }
            )
            continue
        group = groups.setdefault(
            normalized_pn,
            {"old_pn": old_pn, "texture_refs": set(), "texture_ref": texture_ref},
        )
        if texture_ref:
            group["texture_refs"].add(texture_ref)

    profile_files: dict[str, list[Path]] = defaultdict(list)
    for profile_path in profiles_root.iterdir():
        if profile_path.is_file() and profile_path.suffix.casefold() == ".smgstyleset":
            profile_files[profile_path.stem.casefold()].append(profile_path)

    group_status: dict[str, tuple[str, Path | None, list[ET.Element], str]] = {}
    for normalized_pn, group in groups.items():
        texture_refs = group["texture_refs"]
        if not texture_refs:
            group_status[normalized_pn] = ("style_ref_missing", None, [], "Le slot mono-corps est vide.")
            continue
        if len(texture_refs) > 1:
            group_status[normalized_pn] = (
                "style_conflict",
                None,
                [],
                "Plusieurs slots/profils sont associés au même OLD P/N.",
            )
            continue
        texture_ref = next(iter(texture_refs))
        style_stem = _style_stem(texture_ref)
        candidates = profile_files.get(style_stem.casefold(), [])
        if len(candidates) != 1:
            status = "profile_not_found" if not candidates else "profile_ambiguous"
            group_status[normalized_pn] = (
                status,
                None,
                [],
                f"Profil Composer introuvable ou ambigu : {style_stem}.",
            )
            continue
        profile_path = candidates[0]
        try:
            profile_root = ET.parse(profile_path).getroot()
        except (ET.ParseError, OSError) as exc:
            group_status[normalized_pn] = (
                "profile_invalid",
                profile_path,
                [],
                f"Profil illisible ({type(exc).__name__}).",
            )
            continue
        properties = [
            copy.deepcopy(element)
            for element in profile_root
            if _local_name(element.tag) in STYLE_PROPERTY_NAMES
        ]
        if not properties:
            group_status[normalized_pn] = (
                "profile_invalid",
                profile_path,
                [],
                "Le profil ne contient aucune propriété de style prise en charge.",
            )
            continue
        group_status[normalized_pn] = ("ready", profile_path, properties, "")

    files_by_group: dict[str, list[Path]] = {key: [] for key in groups}
    old_pn_patterns = {
        key: _old_pn_pattern(group["old_pn"])
        for key, group in groups.items()
    }
    ambiguous_files: list[tuple[Path, list[str]]] = []
    old_pn_keys = list(groups)
    for piece_path in sorted(pieces_root.rglob("*")):
        if not piece_path.is_file() or piece_path.suffix.casefold() != ".smgxml":
            continue
        candidates = [
            key
            for key in old_pn_keys
            if old_pn_patterns[key] is not None
            and old_pn_patterns[key].search(piece_path.stem)
        ]
        if not candidates:
            continue
        longest = max(len(key) for key in candidates)
        best_matches = [key for key in candidates if len(key) == longest]
        if len(best_matches) == 1:
            files_by_group[best_matches[0]].append(piece_path)
        else:
            ambiguous_files.append((piece_path, best_matches))

    for piece_path, matches in ambiguous_files:
        results.append(
            {
                "old_pn": ", ".join(groups[key]["old_pn"] for key in matches),
                "texture_ref": "",
                "path": str(piece_path),
                "status": "old_pn_ambiguous",
                "actors_total": 0,
                "actors_changed": 0,
                "backup_path": "",
                "message": "Le nom du fichier correspond à plusieurs OLD P/N.",
                "applied": False,
            }
        )

    for normalized_pn, group in groups.items():
        status, profile_path, properties, message = group_status[normalized_pn]
        texture_ref = group["texture_ref"]
        matching_files = files_by_group[normalized_pn]
        if not matching_files:
            results.append(
                {
                    "old_pn": group["old_pn"],
                    "texture_ref": texture_ref,
                    "profile_path": str(profile_path) if profile_path else "",
                    "path": "",
                    "status": "piece_not_found" if status == "ready" else status,
                    "actors_total": 0,
                    "actors_changed": 0,
                    "backup_path": "",
                    "message": "Aucun fichier SMGXML ne correspond à cet OLD P/N."
                    if status == "ready"
                    else message,
                    "applied": False,
                }
            )
            continue

        if status != "ready":
            for piece_path in matching_files:
                results.append(
                    {
                        "old_pn": group["old_pn"],
                        "texture_ref": texture_ref,
                        "profile_path": str(profile_path) if profile_path else "",
                        "path": str(piece_path),
                        "status": status,
                        "actors_total": 0,
                        "actors_changed": 0,
                        "backup_path": "",
                        "message": message,
                        "applied": False,
                    }
                )
            continue

        assert profile_path is not None
        for piece_path in matching_files:
            try:
                tree = ET.parse(piece_path)
            except (ET.ParseError, OSError) as exc:
                results.append(
                    {
                        "old_pn": group["old_pn"],
                        "texture_ref": texture_ref,
                        "profile_path": str(profile_path),
                        "path": str(piece_path),
                        "status": "smgxml_invalid",
                        "actors_total": 0,
                        "actors_changed": 0,
                        "backup_path": "",
                        "message": f"SMGXML illisible ({type(exc).__name__}).",
                        "applied": False,
                    }
                )
                continue

            actors = [
                neutral
                for neutral in tree.getroot().iter()
                if _local_name(neutral.tag) == "Neutral"
                and (_find_child(neutral, "Actor.GeometryType") is not None)
                and _find_child(neutral, "Actor.GeometryType").get("Value") == "1"
            ]
            if not actors:
                results.append(
                    {
                        "old_pn": group["old_pn"],
                        "texture_ref": texture_ref,
                        "profile_path": str(profile_path),
                        "path": str(piece_path),
                        "status": "no_geometry_actor",
                        "actors_total": 0,
                        "actors_changed": 0,
                        "backup_path": "",
                        "message": "Aucun acteur géométrique (GeometryType=1).",
                        "applied": False,
                    }
                )
                continue

            actors_changed = sum(
                1 for actor in actors if _copy_style(actor, properties, profile_path.name)
            )
            backup_path = ""
            if apply and actors_changed:
                try:
                    backup_path = _write_with_backup(tree, piece_path)
                except OSError as exc:
                    results.append(
                        {
                            "old_pn": group["old_pn"],
                            "texture_ref": texture_ref,
                            "profile_path": str(profile_path),
                            "path": str(piece_path),
                            "status": "write_error",
                            "actors_total": len(actors),
                            "actors_changed": actors_changed,
                            "backup_path": "",
                            "message": f"Écriture impossible ({type(exc).__name__}).",
                            "applied": False,
                        }
                    )
                    continue

            results.append(
                {
                    "old_pn": group["old_pn"],
                    "texture_ref": texture_ref,
                    "profile_path": str(profile_path),
                    "path": str(piece_path),
                    "status": "applied" if apply and actors_changed else (
                        "planned" if actors_changed else "already_colored"
                    ),
                    "actors_total": len(actors),
                    "actors_changed": actors_changed,
                    "backup_path": backup_path,
                    "message": "",
                    "applied": bool(apply and actors_changed),
                }
            )

    files_changed = sum(item["status"] in {"planned", "applied"} for item in results)
    return {
        "items": results,
        "summary": {
            "mono_parts": len(mono_parts),
            "files_found": sum(bool(item.get("path")) for item in results),
            "files_changed": files_changed,
            "actors_changed": sum(item["actors_changed"] for item in results),
            "skipped": sum(item["status"] not in {"planned", "applied", "already_colored"} for item in results),
            "applied": bool(apply and any(item["applied"] for item in results)),
        },
    }