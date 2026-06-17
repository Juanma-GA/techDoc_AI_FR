"""Tests Etape 1 - nomenclature .xlsx + DE .zip (fixtures synthetiques)."""

from __future__ import annotations

import zipfile

from openpyxl import Workbook


def _set_input_root(client, root: str) -> None:
    assert client.post("/api/v1/settings", json={"onedrive_input_root": root}).status_code == 200


def _make_xlsx(tmp_path):
    """Nomenclature synthetique (aucune donnee reelle)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Nomenclature"
    ws.append(["Titre du document", None, None, None, None, None])  # ligne parasite
    ws.append(["CATPart", "Designation", "SIN", "Version", "A traiter", "Couleur"])
    ws.append(["PIECE_001.CATPart", "Support avant", "SIN-001", "U320 n", "x", "rouge"])
    ws.append(["PIECE_002.CATPart", "Carter", "SIN-002", "U320 n", "", "0,128,255"])
    ws.append(["PIECE_003.CATPart", "Bielle", "SIN-003", "U320 n-1", "oui", ""])
    p = tmp_path / "nomenclature.xlsx"
    wb.save(p)
    return p


def test_parse_nomenclature(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)
    r = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(xlsx)})
    assert r.status_code == 200, r.text
    body = r.json()
    s = body["summary"]
    assert s["rows"] == 3
    assert s["to_treat"] == 2  # PIECE_001 (x) + PIECE_003 (oui)
    assert s["mono_color"] == 2  # rouge + 0,128,255
    assert "catpart" in s["detected_columns"]

    run_id = body["id"]
    items = client.get(f"/api/v1/identification/{run_id}/items", params={"to_treat": True}).json()
    assert {i["catpart"] for i in items} == {"PIECE_001.CATPart", "PIECE_003.CATPart"}

    mono = client.get(f"/api/v1/identification/{run_id}/items", params={"mono_color": True}).json()
    red = next(i for i in mono if i["sin"] == "SIN-001")
    assert (red["color_r"], red["color_g"], red["color_b"]) == (255, 0, 0)


def test_parse_with_manual_mapping(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)  # en-tete ligne 2 ; cols: 0 CATPart,2 SIN,4 A traiter,5 Couleur
    # Mapping explicite : on designe CATPart=col0, SIN=col2, couleur=col5, sans "a traiter".
    r = client.post("/api/v1/identification/nomenclature", json={
        "scope": "input", "path": str(xlsx),
        "mapping": {"header_row": 2, "catpart": 0, "sin": 2, "color": 5},
    })
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert s["manual_mapping"] is True
    assert s["rows"] == 3
    assert s["to_treat"] == 0  # colonne 'a traiter' non mappee -> tout False
    assert s["mono_color"] == 2

    run_id = r.json()["id"]
    items = client.get(f"/api/v1/identification/{run_id}/items").json()
    # CATPart vient bien de la colonne 0.
    assert {i["catpart"] for i in items} == {"PIECE_001.CATPart", "PIECE_002.CATPart", "PIECE_003.CATPart"}


def test_parse_mapping_requires_catpart(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)
    # Pydantic exige catpart -> 422 si absent.
    r = client.post("/api/v1/identification/nomenclature", json={
        "scope": "input", "path": str(xlsx), "mapping": {"header_row": 2, "sin": 2},
    })
    assert r.status_code == 422


def test_preview_exposes_columns_map(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)
    r = client.post("/api/v1/identification/preview", json={"scope": "input", "path": str(xlsx)})
    cm = r.json()["columns_map"]
    assert cm["catpart"] == 0 and cm["sin"] == 2


def test_export_csv(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)
    run_id = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(xlsx)}).json()["id"]
    r = client.get(f"/api/v1/identification/{run_id}/export.csv", params={"to_treat": True})
    assert r.status_code == 200
    assert r.text.splitlines()[0].startswith("catpart;")
    assert "PIECE_001.CATPart" in r.text


def test_nomenclature_rejects_outside_root(client, tmp_path):
    _set_input_root(client, str(tmp_path / "sub"))
    (tmp_path / "sub").mkdir()
    xlsx = _make_xlsx(tmp_path)  # hors racine
    r = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(xlsx)})
    assert r.status_code == 400
    assert r.json()["code"] == "PATH_OUTSIDE_ROOT"


def test_preview_sheets_and_rows(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    # Classeur a 2 onglets : la nomenclature est sur le 2eme.
    wb = Workbook()
    wb.active.title = "Garde"
    wb.active.append(["Page de garde"])
    ws2 = wb.create_sheet("BD Gestion")
    ws2.append(["Titre", None])
    ws2.append(["CATPart", "SIN", "Couleur"])
    ws2.append(["PIECE_001.CATPart", "SIN-001", "rouge"])
    p = tmp_path / "multi.xlsx"
    wb.save(p)

    # Apercu onglet par defaut (1er).
    r = client.post("/api/v1/identification/preview", json={"scope": "input", "path": str(p)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sheets"] == ["Garde", "BD Gestion"]
    assert body["sheet"] == "Garde"

    # Apercu de l'onglet choisi -> header detecte ligne 2, colonnes reconnues, grille.
    r2 = client.post("/api/v1/identification/preview", json={"scope": "input", "path": str(p), "sheet": "BD Gestion"})
    b2 = r2.json()
    assert b2["sheet"] == "BD Gestion"
    assert b2["header_row_detected"] == 2
    assert "catpart" in b2["columns_detected"]
    assert b2["rows"][1][0] == "CATPart"  # 2eme ligne = en-tete

    # Analyser en designant l'onglet.
    run = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p), "sheet": "BD Gestion"}).json()
    assert run["sheet"] == "BD Gestion"
    assert run["summary"]["rows"] == 1


def test_list_zip(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    z = tmp_path / "DE.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("LEAP-1B/PIECE_001.CATPart", "x")
        zf.writestr("LEAP-1B/PIECE_002.CATPart", "y")
    r = client.post("/api/v1/identification/zip", json={"scope": "input", "path": str(z)})
    assert r.status_code == 200, r.text
    names = {e["name"] for e in r.json()["entries"]}
    assert "LEAP-1B/PIECE_001.CATPart" in names
