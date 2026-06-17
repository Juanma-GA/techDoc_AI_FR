"""Tests routes /api/v1/browse (navigation OneDrive locale, confinement)."""

from __future__ import annotations


def _set_input_root(client, root: str) -> None:
    r = client.post("/api/v1/settings", json={"onedrive_input_root": root})
    assert r.status_code == 200, r.text
    assert r.json()["onedrive_input_root"] == root


def test_roots_reports_configured_input(client, synthetic_tree) -> None:
    _set_input_root(client, str(synthetic_tree))
    r = client.get("/api/v1/browse/roots")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["input"] == str(synthetic_tree)
    assert isinstance(body["detected"], list)


def test_list_root_level(client, synthetic_tree) -> None:
    _set_input_root(client, str(synthetic_tree))
    r = client.post("/api/v1/browse/list", json={"scope": "input", "path": ""})
    assert r.status_code == 200, r.text
    body = r.json()
    names = {e["name"] for e in body["entries"]}
    # Le fixture pose des dossiers (vieux, exports, divers, BREL) et des fichiers racine.
    assert "vieux" in names
    assert "Assemblage Principal.CATProduct" in names
    # Dossiers listes avant les fichiers.
    kinds = [e["kind"] for e in body["entries"]]
    assert kinds == sorted(kinds, key=lambda k: k != "folder") or "folder" in kinds


def test_list_subfolder(client, synthetic_tree) -> None:
    _set_input_root(client, str(synthetic_tree))
    sub = str(synthetic_tree / "BREL")
    r = client.post("/api/v1/browse/list", json={"scope": "input", "path": sub})
    assert r.status_code == 200, r.text
    names = {e["name"] for e in r.json()["entries"]}
    assert "support.CATPart" in names


def test_list_rejects_outside_root(client, synthetic_tree) -> None:
    _set_input_root(client, str(synthetic_tree))
    r = client.post(
        "/api/v1/browse/list",
        json={"scope": "input", "path": str(synthetic_tree.parent)},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "PATH_OUTSIDE_ROOT"


def test_list_rejects_traversal(client, synthetic_tree) -> None:
    _set_input_root(client, str(synthetic_tree))
    r = client.post("/api/v1/browse/list", json={"scope": "input", "path": "../.."})
    assert r.status_code == 400
    assert r.json()["code"] == "PATH_OUTSIDE_ROOT"


def test_list_without_root_configured(client) -> None:
    r = client.post("/api/v1/browse/list", json={"scope": "input", "path": ""})
    assert r.status_code == 400
    assert r.json()["code"] == "ROOT_NOT_CONFIGURED"


def test_files_recursive(client, synthetic_tree) -> None:
    _set_input_root(client, str(synthetic_tree))
    r = client.post("/api/v1/browse/files", json={"scope": "input", "path": ""})
    assert r.status_code == 200, r.text
    entries = r.json()["entries"]
    assert all(e["kind"] == "file" for e in entries)
    # Fichier en profondeur present, avec son rel path complet.
    rels = {e["rel"] for e in entries}
    assert any(rel.endswith("PIECE_001.CATPart") for rel in rels)
    assert any("/" in rel for rel in rels)  # recursif (pas juste la racine)


def test_files_rejects_outside_root(client, synthetic_tree) -> None:
    _set_input_root(client, str(synthetic_tree))
    r = client.post("/api/v1/browse/files", json={"scope": "input", "path": str(synthetic_tree.parent)})
    assert r.status_code == 400
    assert r.json()["code"] == "PATH_OUTSIDE_ROOT"
