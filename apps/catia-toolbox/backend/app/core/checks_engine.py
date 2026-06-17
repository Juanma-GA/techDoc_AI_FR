"""Moteur de verifications configurables sur une arborescence.

Registre de checks deterministes (pures). Chaque check prend (nodes, config)
et renvoie une liste de violations {rule, severity, rel_path, message}.
Inspire du split deterministe de FTM (regles nommees, parametrables).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Iterable

from app.core.parser import ParsedNode
from app.core.tree_metrics import classify_naming

# Registre : nom de regle -> fonction. `AVAILABLE_RULES` expose la liste pour l'UI.
CheckFn = Callable[[list[ParsedNode], dict], list[dict]]

DEFAULT_CONFIG = {
    "max_depth": 6,
    "naming_style": "kebab",
    "forbidden_extensions": ["tmp", "bak", "old"],
}


def _stem(n: ParsedNode) -> str:
    if n.kind == "file" and n.ext:
        return n.name[: -(len(n.ext) + 1)] or n.name
    return n.name


def check_max_depth(nodes: list[ParsedNode], config: dict) -> list[dict]:
    limit = int(config.get("max_depth", DEFAULT_CONFIG["max_depth"]))
    return [
        {"rule": "max_depth", "severity": "warning", "rel_path": n.rel_path,
         "message": f"Profondeur {n.depth} > {limit}."}
        for n in nodes
        if n.kind == "file" and n.depth > limit
    ]


def check_naming(nodes: list[ParsedNode], config: dict) -> list[dict]:
    target = str(config.get("naming_style", DEFAULT_CONFIG["naming_style"]))
    out = []
    for n in nodes:
        style = classify_naming(_stem(n))
        if style != target and style in ("espaces", "majuscules", "snake", "camel"):
            out.append({"rule": "naming", "severity": "info", "rel_path": n.rel_path,
                        "message": f"Nommage '{style}' (cible '{target}')."})
    return out


def check_forbidden_ext(nodes: list[ParsedNode], config: dict) -> list[dict]:
    forbidden = {str(e).lstrip(".").lower() for e in config.get("forbidden_extensions", [])}
    return [
        {"rule": "forbidden_ext", "severity": "danger", "rel_path": n.rel_path,
         "message": f"Extension interdite .{n.ext}."}
        for n in nodes
        if n.kind == "file" and n.ext in forbidden
    ]


def check_duplicates(nodes: list[ParsedNode], _config: dict) -> list[dict]:
    locations: dict[str, list[str]] = defaultdict(list)
    for n in nodes:
        if n.kind == "file":
            locations[n.name.lower()].append(n.rel_path)
    out = []
    for name, paths in locations.items():
        if len(paths) > 1:
            for p in sorted(paths):
                out.append({"rule": "duplicate", "severity": "warning", "rel_path": p,
                            "message": f"Nom '{name}' present {len(paths)} fois."})
    return out


def check_empty_folders(nodes: list[ParsedNode], _config: dict) -> list[dict]:
    parents = {n.parent_path for n in nodes if n.parent_path}
    return [
        {"rule": "empty_folder", "severity": "info", "rel_path": n.rel_path,
         "message": "Dossier sans contenu."}
        for n in nodes
        if n.kind == "folder" and n.rel_path not in parents
    ]


REGISTRY: dict[str, CheckFn] = {
    "max_depth": check_max_depth,
    "naming": check_naming,
    "forbidden_ext": check_forbidden_ext,
    "duplicate": check_duplicates,
    "empty_folder": check_empty_folders,
}
AVAILABLE_RULES = list(REGISTRY.keys())


def run_checks(nodes: Iterable[ParsedNode], config: dict | None = None) -> list[dict]:
    config = {**DEFAULT_CONFIG, **(config or {})}
    enabled = config.get("rules") or AVAILABLE_RULES
    nodes = list(nodes)
    results: list[dict] = []
    for rule in enabled:
        fn = REGISTRY.get(rule)
        if fn:
            results.extend(fn(nodes, config))
    return results


def summarize(results: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {"total": len(results)}
    for r in results:
        out[r["severity"]] = out.get(r["severity"], 0) + 1
    return out
