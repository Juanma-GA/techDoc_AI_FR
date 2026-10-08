"""GET /api/v1/health smoke test."""

from __future__ import annotations


def test_health_ok(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "db" in body
    assert "llm" not in body


def test_settings_routes_are_not_registered(client) -> None:
    openapi = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/settings" not in openapi["paths"]
    assert "/api/v1/settings/test" not in openapi["paths"]
    assert client.get("/api/v1/settings").status_code == 404
