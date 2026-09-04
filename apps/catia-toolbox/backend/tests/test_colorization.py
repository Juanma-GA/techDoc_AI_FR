"""Tests route /api/v1 colorisation des pieces."""

from __future__ import annotations


def _scan(client, path: str) -> str:
    r = client.post("/api/v1/imports/scan", json={"path": path})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_strategies(client) -> None:
    r = client.get("/api/v1/colorization/strategies")
    assert r.status_code == 200
    assert "by_change" in r.json() and "by_type" in r.json()


def test_colorize_by_type(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    r = client.post(f"/api/v1/imports/{imp_id}/colorization", json={"strategy": "by_type"})
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]
    assert r.json()["summary"]["total"] >= 1

    items = client.get(f"/api/v1/colorizations/{run_id}/items").json()
    assert items
    assert all(0 <= it["color_r"] <= 255 for it in items)

    csv = client.get(f"/api/v1/colorizations/{run_id}/export.csv")
    assert csv.status_code == 200
    assert csv.text.splitlines()[0] == "rel_path;r;g;b;reason"

    macro = client.get(f"/api/v1/colorizations/{run_id}/export.macro")
    assert macro.status_code == 200
    assert "SetRealColor" in macro.text

    svg = client.get(f"/api/v1/colorizations/{run_id}/simulation.svg")
    assert svg.status_code == 200
    assert "image/svg+xml" in svg.headers["content-type"]
    assert "<svg" in svg.text and "rgb(" in svg.text

    py = client.get(f"/api/v1/colorizations/{run_id}/export.composer.py")
    assert py.status_code == 200
    assert "text/x-python" in py.headers["content-type"]
    assert "win32com" in py.text and "DRY_RUN = True" in py.text


def test_colorize_by_change_requires_diff(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    r = client.post(f"/api/v1/imports/{imp_id}/colorization", json={"strategy": "by_change"})
    assert r.status_code == 400
    assert r.json()["code"] == "COLOR_DIFF_REQUIRED"


def test_colorize_by_change_from_diff(client, synthetic_tree) -> None:
    base_id = _scan(client, str(synthetic_tree))
    (synthetic_tree / "NEW.CATPart").write_text("x", encoding="utf-8")
    other_id = _scan(client, str(synthetic_tree))
    diff = client.post(
        "/api/v1/diff", json={"base_import_id": base_id, "other_import_id": other_id}
    ).json()

    r = client.post(
        f"/api/v1/imports/{other_id}/colorization",
        json={"strategy": "by_change", "diff_run_id": diff["id"]},
    )
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]
    items = client.get(f"/api/v1/colorizations/{run_id}/items").json()
    # l'ajout NEW.CATPart doit etre colorie en vert (0,176,80)
    added = [it for it in items if it["rel_path"].endswith("NEW.CATPart")]
    assert added and (added[0]["color_r"], added[0]["color_g"], added[0]["color_b"]) == (0, 176, 80)
