"""Tests routes suggestions (PATCH + bulk + ordre des routes)."""

from __future__ import annotations


def _run_with_suggestions(client, synthetic_tree) -> tuple[str, list[dict]]:
    imp_id = client.post("/api/v1/imports/scan", json={"path": str(synthetic_tree)}).json()["id"]
    client.post(f"/api/v1/imports/{imp_id}/optimize", json={"use_llm": False})
    run = client.get(f"/api/v1/imports/{imp_id}/optimize/runs").json()[0]
    suggestions = client.get(f"/api/v1/runs/{run['id']}/suggestions").json()
    return run["id"], suggestions


def test_patch_status(client, synthetic_tree) -> None:
    _run, suggestions = _run_with_suggestions(client, synthetic_tree)
    sid = suggestions[0]["id"]
    r = client.patch(f"/api/v1/suggestions/{sid}", json={"status": "accepted"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"


def test_patch_invalid_status(client, synthetic_tree) -> None:
    _run, suggestions = _run_with_suggestions(client, synthetic_tree)
    sid = suggestions[0]["id"]
    r = client.patch(f"/api/v1/suggestions/{sid}", json={"status": "bogus"})
    assert r.status_code == 400
    assert r.json()["code"] == "SUGGESTION_STATUS_INVALID"


def test_bulk_status_route_resolves_before_param(client, synthetic_tree) -> None:
    run_id, suggestions = _run_with_suggestions(client, synthetic_tree)
    ids = [s["id"] for s in suggestions]
    r = client.post("/api/v1/suggestions/bulk-status", json={"ids": ids, "status": "accepted"})
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == len(ids)

    accepted = client.get(f"/api/v1/runs/{run_id}/suggestions", params={"status": "accepted"}).json()
    assert len(accepted) == len(ids)


def test_filter_by_source(client, synthetic_tree) -> None:
    run_id, _ = _run_with_suggestions(client, synthetic_tree)
    r = client.get(f"/api/v1/runs/{run_id}/suggestions", params={"source": "baseline"})
    assert r.status_code == 200
    assert all(s["source"] == "baseline" for s in r.json())
