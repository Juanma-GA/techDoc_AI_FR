"""Rename references inside a CATIA Composer SMGXML file."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET

from app.core.errors import AppError


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _parse(path: str) -> ET.Element:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise AppError("SMGXML_INVALID", f"SMGXML illisible (XML invalide) : {exc}", status_code=400) from exc
    except OSError as exc:
        raise AppError("SMGXML_NOT_FOUND", "SMGXML introuvable ou illisible.", status_code=400) from exc


def _rename(root: ET.Element, rename_map: dict[str, str]) -> list[dict]:
    changes: list[dict] = []
    for elem in root.iter():
        for attr, value in list(elem.attrib.items()):
            if value in rename_map:
                new = rename_map[value]
                elem.set(attr, new)
                changes.append(
                    {
                        "target": _local(elem.tag),
                        "change_type": "rename",
                        "old_value": value,
                        "new_value": new,
                    }
                )
    return changes


def rename(
    path: str,
    rename_map: dict[str, str],
    *,
    apply: bool = False,
    output_path: str | None = None,
) -> dict:
    tree = ET.ElementTree(_parse(path))
    changes = _rename(tree.getroot(), rename_map)

    backup_path = ""
    written = ""
    if apply and changes:
        out = output_path or path
        if out == path:
            backup_path = path + ".bak"
            shutil.copy2(path, backup_path)
        tree.write(out, encoding="utf-8", xml_declaration=True)
        written = out

    summary = {"operation": "rename", "changes": len(changes), "applied": bool(written)}
    return {
        "changes": changes,
        "applied": bool(written),
        "backup_path": backup_path,
        "output_path": written,
        "summary": summary,
    }
