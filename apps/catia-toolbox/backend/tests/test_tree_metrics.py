"""Tests unitaires purs - heuristiques tree_metrics."""

from __future__ import annotations

from app.core.parser import ParsedNode
from app.core.tree_metrics import classify_naming, compute_metrics


def _node(rel_path: str, kind: str = "file") -> ParsedNode:
    name = rel_path.rsplit("/", 1)[-1]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name and kind == "file" else ""
    parent = rel_path.rsplit("/", 1)[0] if "/" in rel_path else None
    return ParsedNode(
        rel_path=rel_path, name=name, ext=ext, kind=kind, depth=rel_path.count("/"), parent_path=parent
    )


def test_classify_naming() -> None:
    assert classify_naming("mon fichier") == "espaces"
    assert classify_naming("mon_fichier") == "snake"
    assert classify_naming("mon-fichier") == "kebab"
    assert classify_naming("MAJUSCULE") == "majuscules"
    assert classify_naming("monFichier") == "camel"
    assert classify_naming("minuscule") == "minuscules"


def test_compute_metrics_detects_issues() -> None:
    nodes = [
        _node("a/b/c/d/e/f/deep.catpart"),  # nesting profond
        _node("x/piece.catpart"),
        _node("y/piece.catpart"),  # doublon de basename
        _node("Mon Fichier.pdf"),  # espaces
        _node("a", "folder"),
    ]
    m = compute_metrics(nodes, target_max_depth=3)
    assert m["file_count"] == 4
    assert m["max_depth"] >= 6
    assert m["deep_nesting_count"] >= 1
    assert m["duplicate_basenames_count"] >= 1
    assert m["naming"]["inconsistent"] is True
