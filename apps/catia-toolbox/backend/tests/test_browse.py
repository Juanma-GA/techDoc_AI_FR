"""Tests routes /api/v1/browse (navigation OneDrive locale, confinement)."""

from __future__ import annotations

from pathlib import Path


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


def test_list_without_root_uses_local_storage(client) -> None:
    r = client.post("/api/v1/browse/list", json={"scope": "input", "path": ""})
    assert r.status_code == 200, r.text
    assert Path(r.json()["root"]).is_dir()


def test_local_upload_preserves_folder_selection(client) -> None:
    r = client.post(
        "/api/v1/browse/local-upload",
        files=[
            ("files", ("assembly/part-a.CATPart", b"a", "application/octet-stream")),
            ("files", ("assembly/part-b.CATPart", b"bb", "application/octet-stream")),
        ],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["files"]) == 2
    assert all(Path(item["path"]).is_file() for item in body["files"])
    assert {item["rel"] for item in body["files"]} == {
        "assembly/part-a.CATPart",
        "assembly/part-b.CATPart",
    }

    listed = client.post(
        "/api/v1/browse/list",
        json={"scope": "input", "path": str(Path(body["root"]) / "assembly")},
    )
    assert listed.status_code == 200, listed.text
    assert {entry["name"] for entry in listed.json()["entries"]} == {"part-a.CATPart", "part-b.CATPart"}


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


def _make_xlsx(tmp_path):
    """Classeur synthetique a 2 onglets (aucune donnee reelle)."""
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "Garde"
    wb.active.append(["Page de garde"])
    ws2 = wb.create_sheet("Donnees")
    ws2.append(["CATPart", "Designation"])
    ws2.append(["PIECE_001.CATPart", "Support avant"])
    p = tmp_path / "classeur.xlsm"
    wb.save(p)
    return p


def test_preview_sheets_and_rows(client, tmp_path) -> None:
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)

    # Onglet par defaut (le 1er) : liste des onglets + grille de lignes.
    r = client.post("/api/v1/browse/preview", json={"scope": "input", "path": str(xlsx)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sheets"] == ["Garde", "Donnees"]
    assert body["sheet"] == "Garde"
    assert body["rows"][0][0] == "Page de garde"
    # Apercu generique : pas de mapping metier expose.
    assert "columns_map" not in body

    # Onglet choisi -> grille de cet onglet.
    r2 = client.post("/api/v1/browse/preview", json={"scope": "input", "path": str(xlsx), "sheet": "Donnees"})
    b2 = r2.json()
    assert b2["sheet"] == "Donnees"
    assert b2["rows"][0] == ["CATPart", "Designation"]


def test_preview_rejects_non_excel(client, synthetic_tree) -> None:
    _set_input_root(client, str(synthetic_tree))
    target = str(synthetic_tree / "Assemblage Principal.CATProduct")
    r = client.post("/api/v1/browse/preview", json={"scope": "input", "path": target})
    assert r.status_code == 400
    assert r.json()["code"] == "BROWSE_NOT_EXCEL"


def test_preview_rejects_outside_root(client, tmp_path) -> None:
    _set_input_root(client, str(tmp_path / "sub"))
    (tmp_path / "sub").mkdir()
    xlsx = _make_xlsx(tmp_path)  # hors racine
    r = client.post("/api/v1/browse/preview", json={"scope": "input", "path": str(xlsx)})
    assert r.status_code == 400
    assert r.json()["code"] == "PATH_OUTSIDE_ROOT"
