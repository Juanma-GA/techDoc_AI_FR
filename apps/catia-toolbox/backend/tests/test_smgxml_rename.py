"""Tests for the remaining SMGXML rename workflows."""

from __future__ import annotations

from openpyxl import Workbook


def _set_input_root(client, root: str) -> None:
    assert client.post("/api/v1/settings", json={"onedrive_input_root": root}).status_code == 200


def _make_smgxml(tmp_path):
    content = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<Document>\n"
        '  <Reference actorName="OLD_PIECE" />\n'
        '  <Actor name="OLD_PIECE" />\n'
        "</Document>\n"
    )
    path = tmp_path / "engine.smgxml"
    path.write_text(content, encoding="utf-8")
    return path


def test_rename_dryrun(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml(tmp_path)
    response = client.post(
        "/api/v1/smgxml/rename",
        json={
            "scope": "input",
            "path": str(smg),
            "mapping": [{"old": "OLD_PIECE", "new": "NEW_PIECE"}],
            "apply": False,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["changes"] == 2
    assert body["applied"] is False
    changes = client.get(f"/api/v1/smgxml/{body['id']}/changes").json()
    assert all(change["new_value"] == "NEW_PIECE" for change in changes)


def _make_batch_nomen(client, tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["SIN", "OLD P/N", "NEW P/N"])
    ws.append(["030A5", "2469M86P01", "2568M87P02"])
    path = tmp_path / "nomen_batch.xlsx"
    wb.save(path)
    return client.post(
        "/api/v1/identification/nomenclature",
        json={"scope": "input", "path": str(path)},
    ).json()["id"]


def _make_batch_tree(tmp_path):
    composer = tmp_path / "COMPOSER"
    prod = composer / "COMP PROD"
    part = composer / "COMP PART"
    converted = tmp_path / "CONVERTED"
    for directory in (prod, part, converted):
        directory.mkdir(parents=True)
    (prod / "030A5_SPACER-ANTI-MIGRATION.smgXml").write_text(
        '<Document><Ref name="GE_030A5_2469M86P01_P_01" />'
        '<Geom src="GE_030A5_2469M86P01_P_01.smgGeom" /></Document>',
        encoding="utf-8",
    )
    (part / "GE_030A5_2469M86P01_P_01.smgXml").write_text("<old/>", encoding="utf-8")
    (part / "GE_030A5_2469M86P01_P_01.smgGeom").write_text("geom", encoding="utf-8")
    (converted / "GE_030A5_2568M87P02_X000_001.smgXml").write_text("<new/>", encoding="utf-8")
    (converted / "GE_030A5_2568M87P02_X000_001.smgGeom").write_text("geomnew", encoding="utf-8")
    return composer, converted, prod, part


def test_batch_rename_dryrun_then_apply(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    run_id = _make_batch_nomen(client, tmp_path)
    composer, converted, prod, part = _make_batch_tree(tmp_path)
    body = {
        "scope": "input",
        "composer_root": str(composer),
        "converted_root": str(converted),
        "nomenclature_run_id": run_id,
    }

    dry = client.post("/api/v1/smgxml/batch-rename", json=body)
    assert dry.status_code == 200, dry.text
    item = dry.json()["items"][0]
    assert item["status"] == "ok" and item["replacements"] == 2
    assert (part / "GE_030A5_2469M86P01_P_01.smgXml").exists()

    body["apply"] = True
    applied = client.post("/api/v1/smgxml/batch-rename", json=body)
    assert applied.status_code == 200, applied.text
    assert applied.json()["items"][0]["applied"] is True
    assert not (part / "GE_030A5_2469M86P01_P_01.smgXml").exists()
    assert (part / "GE_030A5_2568M87P02_X000_001.smgXml").exists()
    assembly = (prod / "030A5_SPACER-ANTI-MIGRATION.smgXml").read_text(encoding="utf-8")
    assert "GE_030A5_2469M86P01_P_01" not in assembly
    assert assembly.count("GE_030A5_2568M87P02_X000_001") == 2


def test_retired_workflow_routes_are_not_registered(client):
    paths = set(client.get("/api/v1/openapi.json").json()["paths"])
    retired = {
        "/api/v1/imports/{import_id}/tree",
        "/api/v1/imports/{import_id}/optimize",
        "/api/v1/imports/{import_id}/optimize/runs",
        "/api/v1/runs/{run_id}/suggestions",
        "/api/v1/runs/{run_id}/export.csv",
        "/api/v1/runs/{run_id}/export.script",
        "/api/v1/runs/{run_id}/export/save",
        "/api/v1/imports/{import_id}/colorization",
        "/api/v1/colorization/strategies",
        "/api/v1/smgxml/inspect",
        "/api/v1/smgxml/tree",
        "/api/v1/smgxml/recolor",
        "/api/v1/colorref",
    }
    assert retired.isdisjoint(paths)
    assert "/api/v1/smgxml/rename" in paths
    assert "/api/v1/smgxml/batch-rename" in paths
