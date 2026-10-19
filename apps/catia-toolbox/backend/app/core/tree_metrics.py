"""Heuristiques deterministes sur une arborescence.

Fonctions pures (testables sans DB ni reseau) : prennent une liste de
`ParsedNode` et renvoient un dict JSON-serialisable. Elles sont conservees sur
les imports et reutilisees par les verifications de structure.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Iterable

from app.core.parser import ParsedNode


# Seuils par defaut (ajustables via config du run).
DEFAULT_TARGET_MAX_DEPTH = 5
HIGH_FANOUT_THRESHOLD = 40
SCATTERED_EXT_FOLDER_THRESHOLD = 4

_CAMEL_RE = re.compile(r"^[a-z]+(?:[A-Z][a-z0-9]*)+$")
_PASCAL_RE = re.compile(r"^(?:[A-Z][a-z0-9]*){2,}$")


def _stem(node: ParsedNode) -> str:
    if node.kind == "file" and node.ext:
        return node.name[: -(len(node.ext) + 1)] or node.name
    return node.name


def classify_naming(stem: str) -> str:
    """Classe un nom (sans extension) dans un style de nommage."""
    if not stem:
        return "autre"
    if " " in stem:
        return "espaces"
    if "_" in stem:
        return "snake"
    if "-" in stem:
        return "kebab"
    if stem.isupper():
        return "majuscules"
    if _CAMEL_RE.match(stem) or _PASCAL_RE.match(stem):
        return "camel"
    if stem.islower():
        return "minuscules"
    return "autre"


def compute_metrics(
    nodes: Iterable[ParsedNode],
    *,
    target_max_depth: int = DEFAULT_TARGET_MAX_DEPTH,
) -> dict:
    nodes = list(nodes)
    files = [n for n in nodes if n.kind == "file"]
    folders = [n for n in nodes if n.kind == "folder"]

    depths = [n.depth for n in files] or [0]
    max_depth = max((n.depth for n in nodes), default=0)
    avg_depth = round(sum(depths) / len(depths), 2)

    # --- Fan-out : nombre d'enfants directs par dossier (None = racine) ---
    children: dict[str | None, int] = defaultdict(int)
    for n in nodes:
        children[n.parent_path] += 1
    fanouts = list(children.values()) or [0]
    high_fanout = sorted(
        (
            {"folder": p or "(racine)", "children": c}
            for p, c in children.items()
            if c > HIGH_FANOUT_THRESHOLD
        ),
        key=lambda d: d["children"],
        reverse=True,
    )

    # --- Nesting profond ---
    deep_nesting = sorted(
        (n.rel_path for n in nodes if n.depth > target_max_depth)
    )

    # --- Incoherences de nommage ---
    style_counts: Counter[str] = Counter()
    style_examples: dict[str, str] = {}
    for n in nodes:
        style = classify_naming(_stem(n))
        style_counts[style] += 1
        style_examples.setdefault(style, n.rel_path)
    distinct_styles = [s for s in style_counts if style_counts[s] > 0]

    # --- Doublons de noms (meme nom sous parents differents) ---
    name_locations: dict[str, list[str]] = defaultdict(list)
    for n in files:
        name_locations[n.name.lower()].append(n.rel_path)
    duplicate_basenames = sorted(
        (
            {"name": name, "count": len(paths), "paths": sorted(paths)[:10]}
            for name, paths in name_locations.items()
            if len(paths) > 1
        ),
        key=lambda d: d["count"],
        reverse=True,
    )

    # --- Extensions dispersees (presentes dans beaucoup de dossiers) ---
    ext_folders: dict[str, set[str | None]] = defaultdict(set)
    ext_counts: Counter[str] = Counter()
    for n in files:
        if n.ext:
            ext_folders[n.ext].add(n.parent_path)
            ext_counts[n.ext] += 1
    scattered_extensions = sorted(
        (
            {"ext": ext, "folders": len(parents), "files": ext_counts[ext]}
            for ext, parents in ext_folders.items()
            if len(parents) >= SCATTERED_EXT_FOLDER_THRESHOLD
        ),
        key=lambda d: d["folders"],
        reverse=True,
    )

    # --- Types orphelins (extension presente une seule fois) ---
    orphan_types = sorted(ext for ext, c in ext_counts.items() if c == 1)

    return {
        "node_count": len(nodes),
        "file_count": len(files),
        "folder_count": len(folders),
        "max_depth": max_depth,
        "avg_depth": avg_depth,
        "target_max_depth": target_max_depth,
        "max_fanout": max(fanouts),
        "avg_fanout": round(sum(fanouts) / len(fanouts), 2),
        "high_fanout_folders": high_fanout[:20],
        "deep_nesting": deep_nesting[:50],
        "deep_nesting_count": len(deep_nesting),
        "naming": {
            "styles": dict(style_counts),
            "examples": style_examples,
            "inconsistent": len(distinct_styles) > 1,
        },
        "duplicate_basenames": duplicate_basenames[:30],
        "duplicate_basenames_count": len(duplicate_basenames),
        "scattered_extensions": scattered_extensions[:20],
        "orphan_types": orphan_types[:30],
        "extensions": dict(ext_counts.most_common(30)),
    }
