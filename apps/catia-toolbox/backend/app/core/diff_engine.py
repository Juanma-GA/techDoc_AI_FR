"""Comparaison de deux arborescences (detection de pieces modifiees).

Fonction pure : compare deux listes de ParsedNode (fichiers) par chemin relatif
et renvoie les ajouts / suppressions / modifications. Deterministe, sans DB.
"""

from __future__ import annotations

from typing import Iterable

from app.core.parser import ParsedNode


def _files_by_path(nodes: Iterable[ParsedNode]) -> dict[str, ParsedNode]:
    return {n.rel_path: n for n in nodes if n.kind == "file"}


def compare(base: Iterable[ParsedNode], other: Iterable[ParsedNode]) -> list[dict]:
    """Renvoie les differences entre `base` et `other` (du point de vue de other)."""
    base_map = _files_by_path(base)
    other_map = _files_by_path(other)
    entries: list[dict] = []

    for path, node in other_map.items():
        ref = base_map.get(path)
        if ref is None:
            entries.append({"rel_path": path, "change_type": "added", "detail": f"taille {node.size} o"})
            continue
        diffs = []
        if ref.size != node.size:
            diffs.append(f"taille {ref.size} -> {node.size} o")
        if ref.mtime and node.mtime and ref.mtime != node.mtime:
            diffs.append("date modifiee")
        if diffs:
            entries.append({"rel_path": path, "change_type": "modified", "detail": " ; ".join(diffs)})

    for path, node in base_map.items():
        if path not in other_map:
            entries.append({"rel_path": path, "change_type": "removed", "detail": f"taille {node.size} o"})

    entries.sort(key=lambda e: (e["change_type"], e["rel_path"]))
    return entries


def summarize(entries: list[dict]) -> dict[str, int]:
    out = {"added": 0, "removed": 0, "modified": 0}
    for e in entries:
        out[e["change_type"]] = out.get(e["change_type"], 0) + 1
    out["total"] = len(entries)
    return out
