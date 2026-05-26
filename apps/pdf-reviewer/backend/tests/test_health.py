"""Smoke tests for /api/v1/health."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["llm"] in {"configured", "not_configured"}
    assert body["version"] == "0.1.0"


def test_health_propagates_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    rid = response.headers.get("X-Request-Id")
    assert rid and len(rid) >= 16
