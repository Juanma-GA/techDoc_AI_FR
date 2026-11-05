"""Smoke tests for /api/v1/health — covers the happy path + request-id propagation
+ the 4-state LLM badge logic (ok / untested / not_configured / disabled)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.mistral_client import save_settings, set_llm_enabled, set_llm_tested
from app.db.models import File, FileVersion, Project
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


def test_connectivity_rechecks_missing_sources_and_ai_switch(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "synthetic.txt"
    source.write_text("Synthetic fixture", encoding="utf-8")
    with SessionLocal() as db:
        project = Project(
            name="Synthetic connectivity",
            reference_path=str(source),
            basl_path=str(tmp_path / "missing.xlsx"),
            corpus_path=str(tmp_path),
        )
        db.add(project)
        db.flush()
        document = File(project_id=project.id, current_name="synthetic.txt")
        db.add(document)
        db.flush()
        db.add(
            FileVersion(
                file_id=document.id, filename="synthetic.txt", storage_path=str(source), sha256="a" * 64
            )
        )
        set_llm_enabled(db, False)
        db.commit()
    response = client.get("/api/v1/health/connectivity")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    assert body["sources"]["documents"]["available"] == 1
    assert body["sources"]["folder"]["available"] == 1
    assert body["sources"]["reference"]["available"] == 1
    assert body["sources"]["basl"]["unavailable"] == 1
    assert body["ai_enabled"] is False
    assert body["ai_connection"] == "disabled"
    source.unlink()
    updated = client.get("/api/v1/health/connectivity").json()
    assert updated["sources"]["documents"]["unavailable"] == 1
    assert updated["sources"]["reference"]["unavailable"] == 1
    assert updated["checked_at"] != body["checked_at"]


@pytest.mark.parametrize(("status", "expected"), [(200, "connected"), (401, "rejected"), (503, "rejected")])
def test_connectivity_provider_probe(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, status: int, expected: str
) -> None:
    with SessionLocal() as db:
        save_settings(db, {"api_key": "synthetic-key", "base_url": "https://provider.invalid/"})
        set_llm_tested(db, True)
    probe = AsyncMock(return_value=httpx.Response(status))
    monkeypatch.setattr(httpx.AsyncClient, "get", probe)
    body = client.get("/api/v1/health/connectivity").json()
    assert body["ai_enabled"] is True
    assert body["ai_connection"] == expected
    assert probe.call_args.args[0] == "https://provider.invalid/v1/models"
    assert client.get("/api/v1/health").json()["llm"] == ("ok" if status == 200 else "untested")
    with SessionLocal() as db:
        set_llm_enabled(db, False)
    probe.reset_mock()
    assert client.get("/api/v1/health/connectivity").json()["ai_connection"] == "disabled"
    probe.assert_not_called()


def test_connectivity_provider_timeout(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    with SessionLocal() as db:
        save_settings(db, {"api_key": "synthetic-key"})
        set_llm_tested(db, True)
    monkeypatch.setattr(
        httpx.AsyncClient, "get", AsyncMock(side_effect=httpx.ConnectTimeout("Synthetic timeout"))
    )
    assert client.get("/api/v1/health/connectivity").json()["ai_connection"] == "unreachable"
    assert client.get("/api/v1/health").json()["llm"] == "untested"


def test_connectivity_permission_denied_and_wrong_type(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with SessionLocal() as db:
        db.add(Project(name="Synthetic permissions", reference_path=str(tmp_path), corpus_path=str(tmp_path)))
        db.commit()
    monkeypatch.setattr("app.api.health.os.access", lambda *args: False)
    body = client.get("/api/v1/health/connectivity").json()
    assert body["sources"]["reference"]["unavailable"] == 1
    assert body["sources"]["folder"]["unavailable"] == 1
