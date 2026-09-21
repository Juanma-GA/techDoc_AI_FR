"""GET /api/v1/health smoke test."""

from __future__ import annotations

import json


def test_health_ok(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "db" in body
    assert "llm" in body


def test_api_request_is_logged(capsys, client) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-Id": "test-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "test-request"
    record = next(
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if '"event": "api_request"' in line
    )
    assert record["method"] == "GET"
    assert record["path"] == "/api/v1/health"
    assert record["status_code"] == 200
    assert record["duration_ms"] >= 0
    assert record["request_id"] == "test-request"
