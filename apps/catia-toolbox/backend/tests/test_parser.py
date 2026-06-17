"""Tests unitaires purs - parser (scan dossier + listing)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import AppError
from app.core.parser import parse_listing, scan_folder


def test_scan_folder_metadata_only(synthetic_tree) -> None:
    tree = scan_folder(str(synthetic_tree))
    assert tree.node_count > 0
    paths = {n.rel_path for n in tree.nodes}
    assert "Assemblage Principal.CATProduct" in paths
    assert any(n.kind == "folder" for n in tree.nodes)
    assert any(n.kind == "file" for n in tree.nodes)
    # parent_path coherent
    deep = next(n for n in tree.nodes if n.rel_path.endswith("encore/PIECE_001.CATPart"))
    assert deep.parent_path == "vieux/v1/sous/profond/encore"
    assert deep.ext == "catpart"
    assert deep.depth == 5


def test_scan_folder_missing_path() -> None:
    with pytest.raises(AppError) as exc:
        scan_folder("/chemin/qui/n/existe/pas/vraiment")
    assert exc.value.code == "SCAN_PATH_NOT_FOUND"


def test_scan_folder_max_nodes(synthetic_tree) -> None:
    with pytest.raises(AppError) as exc:
        scan_folder(str(synthetic_tree), max_nodes=2)
    assert exc.value.code == "TREE_TOO_LARGE"


def test_parse_listing_csv() -> None:
    raw = (Path(__file__).parent / "fixtures" / "listing.csv").read_bytes()
    tree = parse_listing(raw, "csv")
    paths = {n.rel_path for n in tree.nodes}
    assert "BREL/support.CATPart" in paths
    # dossiers synthetises depuis les prefixes
    assert "vieux/v1/sous/profond/encore" in paths
    assert "vieux" in paths


def test_parse_listing_json() -> None:
    raw = (Path(__file__).parent / "fixtures" / "listing.json").read_bytes()
    tree = parse_listing(raw, "json")
    files = [n for n in tree.nodes if n.kind == "file"]
    assert any(n.rel_path == "exports/PIECE_001.CATPart" for n in files)


def test_parse_listing_unsupported_ext() -> None:
    with pytest.raises(AppError) as exc:
        parse_listing(b"x", "txt")
    assert exc.value.code == "LISTING_EXT_UNSUPPORTED"
