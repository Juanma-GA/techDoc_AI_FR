"""Routes /api/v1/flows : CRUD + export d'un logigramme sauvegarde."""

from __future__ import annotations

import uuid


def _create(client, sample_dsl: str) -> dict:
    graph = client.post("/api/v1/parse/json", json={"content": sample_dsl}).json()["graph"]
    res = client.post(
        "/api/v1/flows",
        json={"name": "Panne charge", "source_type": "dsl", "source_text": sample_dsl, "graph": graph},
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_list_flows_empty(client) -> None:
    res = client.get("/api/v1/flows")
    assert res.status_code == 200
    assert res.json() == []


def test_create_flow(client, sample_dsl) -> None:
    body = _create(client, sample_dsl)
    uuid.UUID(body["id"], version=4)
    assert body["node_count"] == 6
    assert body["graph"]["fault_code"] == "P0562"


def test_get_flow_and_404(client, sample_dsl) -> None:
    created = _create(client, sample_dsl)
    assert client.get(f"/api/v1/flows/{created['id']}").json()["name"] == "Panne charge"
    missing = client.get(f"/api/v1/flows/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "FLOW_NOT_FOUND"
    assert "request_id" in missing.json()


def test_update_flow(client, sample_dsl) -> None:
    created = _create(client, sample_dsl)
    res = client.put(f"/api/v1/flows/{created['id']}", json={"name": "Renomme"})
    assert res.status_code == 200
    assert res.json()["name"] == "Renomme"
    assert res.json()["node_count"] == 6


def test_delete_flow(client, sample_dsl) -> None:
    created = _create(client, sample_dsl)
    assert client.delete(f"/api/v1/flows/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/flows/{created['id']}").status_code == 404


def test_export_saved_flow(client, sample_dsl) -> None:
    created = _create(client, sample_dsl)
    res = client.get(f"/api/v1/flows/{created['id']}/export/mermaid")
    assert res.status_code == 200
    assert 'filename="Panne_charge.mmd"' in res.headers["content-disposition"]
    assert "flowchart TD" in res.text
    assert client.get(f"/api/v1/flows/{created['id']}/export/visio").status_code == 404


def test_list_and_stats_after_create(client, sample_dsl) -> None:
    _create(client, sample_dsl)
    assert len(client.get("/api/v1/flows").json()) == 1
    stats = client.get("/api/v1/admin/stats").json()
    assert stats["flows"] == 1
    assert stats["nodes"] == 6


def test_reset_all(client, sample_dsl) -> None:
    _create(client, sample_dsl)
    res = client.post("/api/v1/admin/reset/all")
    assert res.status_code == 200
    assert client.get("/api/v1/flows").json() == []


def test_reset_flows_scope(client, sample_dsl) -> None:
    _create(client, sample_dsl)
    assert client.post("/api/v1/admin/reset/flows").status_code == 200
    assert client.get("/api/v1/admin/stats").json()["flows"] == 0
