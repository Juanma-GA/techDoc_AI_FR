"""Tests pour /api/v1/projects (Sprint S0)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.session import Base, engine
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    # Tests run on in-memory SQLite (cf. tests/conftest.py).
    # Re-create schema for each session — fast, isolated.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(create_app())


def test_create_project_returns_201_and_uuid(client: TestClient) -> None:
    r = client.post("/api/v1/projects", json={"name": "P1", "description": "demo"})
    assert r.status_code == 201, r.text
    body = r.json()
    uuid.UUID(body["id"])  # parses as UUID
    assert body["name"] == "P1"
    assert body["description"] == "demo"
    assert body["vision_enabled"] is False


def test_list_projects_returns_created_first(client: TestClient) -> None:
    client.post("/api/v1/projects", json={"name": "A"})
    client.post("/api/v1/projects", json={"name": "B"})
    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    items = r.json()
    assert {p["name"] for p in items} == {"A", "B"}


def test_create_duplicate_name_returns_409_with_unified_error(client: TestClient) -> None:
    client.post("/api/v1/projects", json={"name": "P-dup"})
    r = client.post("/api/v1/projects", json={"name": "P-dup"})
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "PROJECT_NAME_TAKEN"
    assert body["message"]
    assert body["request_id"]


def test_get_unknown_project_returns_404_with_unified_error(client: TestClient) -> None:
    fake = uuid.uuid4()
    r = client.get(f"/api/v1/projects/{fake}")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "PROJECT_NOT_FOUND"
    assert body["detail"]["id"] == str(fake)


def test_get_invalid_uuid_returns_422(client: TestClient) -> None:
    r = client.get("/api/v1/projects/not-a-uuid")
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_update_project_changes_fields(client: TestClient) -> None:
    created = client.post("/api/v1/projects", json={"name": "P-upd"}).json()
    pid = created["id"]
    r = client.put(
        f"/api/v1/projects/{pid}",
        json={"description": "ok", "vision_enabled": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["description"] == "ok"
    assert body["vision_enabled"] is True
    assert body["name"] == "P-upd"  # unchanged


def test_delete_project_returns_204(client: TestClient) -> None:
    created = client.post("/api/v1/projects", json={"name": "P-del"}).json()
    pid = created["id"]
    r = client.delete(f"/api/v1/projects/{pid}")
    assert r.status_code == 204
    assert client.get(f"/api/v1/projects/{pid}").status_code == 404


def test_create_with_empty_name_returns_422(client: TestClient) -> None:
    r = client.post("/api/v1/projects", json={"name": ""})
    assert r.status_code == 422
