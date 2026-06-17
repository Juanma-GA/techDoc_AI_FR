"""Tests route /api/v1 conversion CATIA 3D -> Composer."""

from __future__ import annotations


def _scan(client, path: str) -> str:
    r = client.post("/api/v1/imports/scan", json={"path": path})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_conversion_plan(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    r = client.post(f"/api/v1/imports/{imp_id}/conversion", json={})
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]
    assert r.json()["summary"]["total"] >= 1

    items = client.get(f"/api/v1/conversions/{run_id}/items").json()
    assert items
    assert all(it["target_path"].endswith(".smg") for it in items)

    csv = client.get(f"/api/v1/conversions/{run_id}/export.csv")
    assert csv.status_code == 200
    assert csv.text.splitlines()[0] == "source_path;target_path;source_ext"

    script = client.get(f"/api/v1/conversions/{run_id}/export.script")
    assert script.status_code == 200
    assert "text/x-python" in script.headers["content-type"]
    body = script.text
    assert "win32com" in body
    assert "DRY_RUN = True" in body
    assert "PLAN = [" in body
    # le plan embarque doit referencer une cible .smg
    assert ".smg" in body
