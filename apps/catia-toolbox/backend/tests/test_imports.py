"""Tests routes /api/v1/imports."""

from __future__ import annotations

import io
from pathlib import Path


def _scan(client, path: str):
    return client.post("/api/v1/imports/scan", json={"path": path})


def test_scan_folder(client, synthetic_tree) -> None:
    r = _scan(client, str(synthetic_tree))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["node_count"] > 0
    assert body["source_mode"] == "folder"
    assert body["metrics"]["file_count"] >= 1


def test_scan_path_not_found(client) -> None:
    r = _scan(client, "/nope/does/not/exist/xyz")
    assert r.status_code == 404
    assert r.json()["code"] == "SCAN_PATH_NOT_FOUND"


def test_scan_max_nodes(client, synthetic_tree) -> None:
    r = client.post("/api/v1/imports/scan", json={"path": str(synthetic_tree), "max_nodes": 1})
    assert r.status_code == 413
    assert r.json()["code"] == "TREE_TOO_LARGE"


def test_upload_csv_then_list_and_delete(client) -> None:
    raw = (Path(__file__).parent / "fixtures" / "listing.csv").read_bytes()
    r = client.post(
        "/api/v1/imports/upload",
        files={"file": ("listing.csv", io.BytesIO(raw), "text/csv")},
    )
    assert r.status_code == 200, r.text
    imp_id = r.json()["id"]
    assert r.json()["source_mode"] == "csv"

    listing = client.get("/api/v1/imports")
    assert any(i["id"] == imp_id for i in listing.json())

    got = client.get(f"/api/v1/imports/{imp_id}")
    assert got.status_code == 200

    deleted = client.delete(f"/api/v1/imports/{imp_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/imports/{imp_id}").status_code == 404


def test_upload_json(client) -> None:
    raw = (Path(__file__).parent / "fixtures" / "listing.json").read_bytes()
    r = client.post(
        "/api/v1/imports/upload",
        files={"file": ("listing.json", io.BytesIO(raw), "application/json")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["source_mode"] == "json"


def test_upload_rejects_bad_ext(client) -> None:
    r = client.post(
        "/api/v1/imports/upload",
        files={"file": ("data.txt", io.BytesIO(b"x"), "text/plain")},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "FILE_EXT_NOT_ALLOWED"


def _set_input_root(client, root: str) -> None:
    assert client.post(
        "/api/v1/settings", json={"onedrive_input_root": root}
    ).status_code == 200


def test_select_mixed_file_and_folder(client, synthetic_tree) -> None:
    _set_input_root(client, str(synthetic_tree))
    paths = [
        str(synthetic_tree / "Assemblage Principal.CATProduct"),  # fichier racine
        str(synthetic_tree / "BREL"),  # dossier (scan recursif)
    ]
    r = client.post("/api/v1/imports/select", json={"scope": "input", "paths": paths})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_mode"] == "selection"
    assert body["node_count"] >= 3  # le fichier + dossier BREL + ses 2 fichiers


def test_select_rejects_outside_root(client, synthetic_tree) -> None:
    _set_input_root(client, str(synthetic_tree))
    r = client.post(
        "/api/v1/imports/select",
        json={"scope": "input", "paths": [str(synthetic_tree.parent)]},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "PATH_OUTSIDE_ROOT"


def test_select_without_root(client, synthetic_tree) -> None:
    r = client.post(
        "/api/v1/imports/select",
        json={"scope": "input", "paths": [str(synthetic_tree)]},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "ROOT_NOT_CONFIGURED"
