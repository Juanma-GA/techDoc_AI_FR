"""Tests Etapes 3 & 4 - SMGXML recolor / rename (fixtures synthetiques)."""

from __future__ import annotations

from openpyxl import Workbook


def _set_input_root(client, root: str) -> None:
    assert client.post("/api/v1/settings", json={"onedrive_input_root": root}).status_code == 200


def _make_smgxml(tmp_path):
    content = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<Document>\n"
        '  <Actor name="SIN-001" color="" />\n'
        '  <Actor name="SIN-002" color="0,0,0" />\n'
        '  <Reference actorName="OLD_PIECE" />\n'
        '  <Actor name="OLD_PIECE" color="" />\n'
        "</Document>\n"
    )
    p = tmp_path / "engine.smgxml"
    p.write_text(content, encoding="utf-8")
    return p


def _make_nomenclature(client, tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["CATPart", "SIN", "Couleur"])
    ws.append(["PIECE_001.CATPart", "SIN-001", "255,0,0"])
    ws.append(["PIECE_002.CATPart", "SIN-002", ""])
    p = tmp_path / "nomen.xlsx"
    wb.save(p)
    return client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()["id"]


def test_inspect(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml(tmp_path)
    r = client.post("/api/v1/smgxml/inspect", json={"scope": "input", "path": str(smg)})
    assert r.status_code == 200, r.text
    names = {a["name"] for a in r.json()}
    assert {"SIN-001", "SIN-002", "OLD_PIECE"} <= names


def test_recolor_dryrun_then_apply(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml(tmp_path)
    nom_id = _make_nomenclature(client, tmp_path)

    # Dry-run : 1 changement (SIN-001 vide -> 255,0,0), rien ecrit.
    r = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id, "match_by": "sin", "apply": False,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["changes"] == 1
    assert body["applied"] is False
    assert "255,0,0" not in smg.read_text(encoding="utf-8")  # rien ecrit

    # Apply : ecrit le fichier + cree un .bak.
    r2 = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id, "match_by": "sin", "apply": True,
    })
    assert r2.status_code == 200, r2.text
    assert r2.json()["applied"] is True
    assert "255,0,0" in smg.read_text(encoding="utf-8")
    assert (tmp_path / "engine.smgxml.bak").exists()


def test_rename_dryrun(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml(tmp_path)
    r = client.post("/api/v1/smgxml/rename", json={
        "scope": "input", "path": str(smg),
        "mapping": [{"old": "OLD_PIECE", "new": "NEW_PIECE"}],
        "apply": False,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    # 2 occurrences : Reference@actorName + Actor@name.
    assert body["summary"]["changes"] == 2
    assert body["applied"] is False
    run_id = body["id"]
    changes = client.get(f"/api/v1/smgxml/{run_id}/changes").json()
    assert all(c["new_value"] == "NEW_PIECE" for c in changes)


def test_recolor_no_mono(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml(tmp_path)
    wb = Workbook()
    ws = wb.active
    ws.append(["CATPart", "SIN", "Couleur"])
    ws.append(["P.CATPart", "SIN-009", ""])  # pas de couleur
    p = tmp_path / "nomono.xlsx"
    wb.save(p)
    nom_id = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()["id"]
    r = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id, "apply": False,
    })
    assert r.status_code == 400
    assert r.json()["code"] == "NO_MONO_COLOR"
