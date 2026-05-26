"""Smoke tests for /api/v1/health — covers the happy path + request-id propagation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_returns_200_with_expected_shape(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["llm"] in {"configured", "not_configured"}
    assert body["version"] == "4.0.0"


def test_health_response_carries_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    rid = response.headers.get("X-Request-Id")
    assert rid, "X-Request-Id header must be set on every response"
    assert len(rid) >= 16, "request id should be a uuid hex"


def test_health_honours_inbound_request_id(client: TestClient) -> None:
    custom = "test-request-id-1234567890abcdef"
    response = client.get("/api/v1/health", headers={"X-Request-Id": custom})
    assert response.status_code == 200
    assert response.headers.get("X-Request-Id") == custom
