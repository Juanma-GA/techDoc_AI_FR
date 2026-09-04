"""Tests route /api/v1/imports/{id}/optimize (SSE, chemin baseline)."""

from __future__ import annotations


def _scan(client, path: str) -> str:
    r = client.post("/api/v1/imports/scan", json={"path": path})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_optimize_baseline_creates_suggestions(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))

    # use_llm=false : pas de Mistral requis, chemin baseline deterministe.
    r = client.post(f"/api/v1/imports/{imp_id}/optimize", json={"use_llm": False})
    assert r.status_code == 200, r.text
    stream = r.text
    assert "event: session" in stream
    assert "event: done" in stream

    runs = client.get(f"/api/v1/imports/{imp_id}/optimize/runs").json()
    assert runs, "au moins un run"
    run = runs[0]
    assert run["status"] == "completed"

    suggestions = client.get(f"/api/v1/runs/{run['id']}/suggestions").json()
    assert suggestions, "le baseline doit produire des suggestions"
    assert all(s["source"] == "baseline" for s in suggestions)


def test_optimize_import_404(client) -> None:
    r = client.post(
        "/api/v1/imports/00000000-0000-0000-0000-000000000000/optimize",
        json={"use_llm": False},
    )
    assert r.status_code == 404
