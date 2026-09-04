"""Tests route /api/v1 verifications."""

from __future__ import annotations


def _scan(client, path: str) -> str:
    r = client.post("/api/v1/imports/scan", json={"path": path})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_available_rules(client) -> None:
    r = client.get("/api/v1/checks/rules")
    assert r.status_code == 200
    assert "duplicate" in r.json()


def test_run_check_finds_violations(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    r = client.post(f"/api/v1/imports/{imp_id}/check", json={"max_depth": 3})
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]
    summary = r.json()["summary"]
    assert summary["total"] >= 1

    results = client.get(f"/api/v1/checks/{run_id}/results").json()
    rules = {x["rule"] for x in results}
    # arborescence factice : doublon de basename + nesting profond attendus
    assert "duplicate" in rules or "max_depth" in rules

    csv = client.get(f"/api/v1/checks/{run_id}/export.csv")
    assert csv.status_code == 200
    assert csv.text.splitlines()[0] == "rule;severity;rel_path;message"


def test_check_import_404(client) -> None:
    r = client.post(
        "/api/v1/imports/00000000-0000-0000-0000-000000000000/check", json={}
    )
    assert r.status_code == 404
