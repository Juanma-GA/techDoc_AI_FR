"""Smoke tests for /api/v1/health + LLM 4-state badge logic."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _llm_state(client: TestClient) -> str:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    return response.json()["llm"]


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["llm"] in {"configured", "not_configured", "untested", "disabled"}
    assert body["version"]


def test_health_propagates_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    rid = response.headers.get("X-Request-Id")
    assert rid and len(rid) >= 16


def test_llm_state_not_configured_without_key(client: TestClient) -> None:
    """No effective key (test env has empty MISTRAL_API_KEY) -> not_configured."""
    from app.core import mistral_settings
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        mistral_settings.set_llm_enabled(db, True)
        mistral_settings.save(db, {"api_key": ""})
    finally:
        db.close()
    assert _llm_state(client) == "not_configured"


def test_llm_state_untested_then_configured(client: TestClient) -> None:
    """Key present + enabled but no successful test -> untested; once the
    tested flag flips true -> configured (green). Saving the key invalidates
    the test (back to untested)."""
    from app.core import mistral_settings
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        mistral_settings.set_llm_enabled(db, True)
        # Writing a key resets the tested flag -> untested.
        mistral_settings.save(db, {"api_key": "sk-test-key"})
        assert mistral_settings.get_llm_tested(db) is False
    finally:
        db.close()
    assert _llm_state(client) == "untested"

    db = SessionLocal()
    try:
        mistral_settings.set_llm_tested(db, True)
    finally:
        db.close()
    assert _llm_state(client) == "configured"

    # A subsequent key change must invalidate the test -> untested again.
    db = SessionLocal()
    try:
        mistral_settings.save(db, {"api_key": "sk-other-key"})
        assert mistral_settings.get_llm_tested(db) is False
    finally:
        db.close()
    assert _llm_state(client) == "untested"


def test_llm_state_disabled_overrides(client: TestClient) -> None:
    """Switch OFF wins over a configured + tested key."""
    from app.core import mistral_settings
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        mistral_settings.save(db, {"api_key": "sk-test-key"})
        mistral_settings.set_llm_tested(db, True)
        mistral_settings.set_llm_enabled(db, False)
    finally:
        db.close()
    assert _llm_state(client) == "disabled"

    # Re-enable for hygiene so order-independent runs don't leak OFF state.
    db = SessionLocal()
    try:
        mistral_settings.set_llm_enabled(db, True)
    finally:
        db.close()
