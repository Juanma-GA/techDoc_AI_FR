"""Liveness and active API surface."""

from __future__ import annotations


def test_health_ok(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "version", "db"}
    assert body["status"] == "ok"
    assert body["db"] == "ok"


def test_removed_modules_are_not_exposed(client) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/settings/test" not in paths
    for operations in paths.values():
        for operation in operations.values():
            assert not {"checks", "qc", "replacement"}.intersection(operation.get("tags", []))
