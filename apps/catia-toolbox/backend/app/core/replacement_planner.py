"""Plan de remplacement de pieces (dry-run).

A partir d'un mapping (old_ref -> new_ref) fourni par l'utilisateur, repere
les occurrences dans l'arborescence et propose un plan de remplacement.
Genere un CSV + une macro CATIA squelette (commentee, jamais executee).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Iterable

from app.core.errors import AppError
from app.core.parser import ParsedNode


def parse_mapping(raw: bytes, ext: str) -> list[dict]:
    """Parse un mapping old->new depuis CSV (old;new) ou JSON [{old,new}]."""
    ext = ext.lstrip(".").lower()
    text = raw.decode("utf-8-sig", errors="replace")
    pairs: list[dict] = []
    if ext == "csv":
        sample = text[:2048]
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        for row in csv.DictReader(io.StringIO(text), delimiter=delimiter):
            norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            old = norm.get("old") or norm.get("old_ref") or norm.get("ancien")
            new = norm.get("new") or norm.get("new_ref") or norm.get("nouveau")
            if old and new:
                pairs.append({"old_ref": old, "new_ref": new})
    elif ext == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise AppError("MAPPING_JSON_INVALID", f"JSON invalide : {e}", status_code=400) from e
        if isinstance(data, dict):
            data = data.get("mapping") or data.get("pairs") or []
        for item in data if isinstance(data, list) else []:
            if isinstance(item, dict):
                old = item.get("old") or item.get("old_ref") or item.get("ancien")
                new = item.get("new") or item.get("new_ref") or item.get("nouveau")
                if old and new:
                    pairs.append({"old_ref": str(old), "new_ref": str(new)})
    else:
        raise AppError("MAPPING_EXT_UNSUPPORTED", "Mapping attendu : csv ou json.", status_code=400)
    if not pairs:
        raise AppError("MAPPING_EMPTY", "Mapping vide (colonnes old/new attendues).", status_code=400)
    return pairs


def plan(nodes: Iterable[ParsedNode], mapping: list[dict]) -> list[dict]:
    """Pour chaque (old_ref, new_ref), repere les fichiers correspondants.

    Match : old_ref egal au nom de fichier, ou sous-chaine du chemin relatif.
    """
    items: list[dict] = []
    files = [n for n in nodes if n.kind == "file"]
    for pair in mapping:
        old = pair["old_ref"]
        old_l = old.lower()
        for n in files:
            if n.name.lower() == old_l or old_l in n.rel_path.lower():
                items.append(
                    {"occurrence_path": n.rel_path, "old_ref": old, "new_ref": pair["new_ref"]}
                )
    items.sort(key=lambda i: (i["old_ref"], i["occurrence_path"]))
    return items


def summarize(items: list[dict]) -> dict[str, int]:
    refs = {i["old_ref"] for i in items}
    return {"total": len(items), "distinct_refs": len(refs)}


def _attr(s: Any, key: str) -> str:
    return str(s.get(key, "") if isinstance(s, dict) else getattr(s, key, ""))


def to_csv(items: Iterable[Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["occurrence_path", "old_ref", "new_ref"])
    for it in items:
        w.writerow([_attr(it, "occurrence_path"), _attr(it, "old_ref"), _attr(it, "new_ref")])
    return buf.getvalue()


def to_macro(items: Iterable[Any]) -> str:
    """Squelette de macro CATIA (VBScript) commente - a relire et adapter."""
    lines = [
        "' ============================================================",
        "' Macro de remplacement de pieces - Catia Toolbox (squelette)",
        "' DRY-RUN : relisez et adaptez AVANT execution dans CATIA.",
        "' Ce script ne fait qu'illustrer les remplacements proposes.",
        "' ============================================================",
        "Sub CATMain()",
        "  ' Dim oSel As Selection : Set oSel = CATIA.ActiveDocument.Selection",
        "",
    ]
    count = 0
    for it in items:
        occ = _attr(it, "occurrence_path").replace('"', "")
        old = _attr(it, "old_ref").replace('"', "")
        new = _attr(it, "new_ref").replace('"', "")
        if not old or not new:
            continue
        count += 1
        lines.append(f"  ' Remplacer \"{old}\" par \"{new}\" dans {occ}")
        lines.append(f'  Call ReplacePart("{old}", "{new}")')
        lines.append("")
    if count == 0:
        lines.append("  ' Aucune occurrence a remplacer.")
    lines.append("End Sub")
    return "\r\n".join(lines) + "\r\n"
