"""Smoke tests for /api/v1/health — covers the happy path + request-id propagation
+ the 4-state LLM badge logic (ok / untested / not_configured / disabled)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.mistral_client import save_settings, set_llm_tested
from app.db.session import Base, SessionLocal, engine
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(create_app())


def test_health_returns_200_with_expected_shape(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    # No key configured (conftest forces MISTRAL_API_KEY="") -> not_configured.
    assert body["llm"] in {"ok", "untested", "not_configured", "disabled"}
    assert body["version"] == "4.0.0"


def test_health_untested_when_key_present_but_not_tested(client: TestClient) -> None:
    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-test-1234567890"})
    finally:
        db.close()
    body = client.get("/api/v1/health").json()
    # Key configured + LLM enabled (default) but no successful test yet.
    assert body["llm"] == "untested"


def test_health_ok_after_set_llm_tested_true(client: TestClient) -> None:
    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-test-1234567890"})
        set_llm_tested(db, True)
    finally:
        db.close()
    body = client.get("/api/v1/health").json()
    assert body["llm"] == "ok"


def test_save_settings_new_api_key_resets_tested_flag(client: TestClient) -> None:
    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-test-1234567890"})
        set_llm_tested(db, True)
    finally:
        db.close()
    assert client.get("/api/v1/health").json()["llm"] == "ok"

    # Changing the key invalidates the previous successful test.
    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-rotated-0987654321"})
    finally:
        db.close()
    assert client.get("/api/v1/health").json()["llm"] == "untested"


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
