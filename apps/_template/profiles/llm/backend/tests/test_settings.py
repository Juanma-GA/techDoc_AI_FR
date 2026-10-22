"""Settings API tests for the persisted demo-mode preference."""

from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.mistral_client as mistral_client
from app.db.session import Base, get_db
from app.main import create_app


@pytest.fixture
def demo_client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_demo_mode_defaults_to_normal(demo_client: TestClient) -> None:
    response = demo_client.get("/api/v1/settings")

    assert response.status_code == 200
    assert response.json()["demo_enabled"] is False


def test_demo_mode_setting_persists(demo_client: TestClient) -> None:
    response = demo_client.post("/api/v1/settings", json={"demo_enabled": True})

    assert response.status_code == 200
    assert response.json()["demo_enabled"] is True
    assert response.json()["llm_enabled"] is True

    persisted = demo_client.get("/api/v1/settings")
    assert persisted.status_code == 200
    assert persisted.json()["demo_enabled"] is True


def _save_mistral_settings(client: TestClient, *, embed_model: str) -> None:
    response = client.post(
        "/api/v1/settings",
        json={
            "api_key": "synthetic-test-key",
            "base_url": "https://mistral.test",
            "chat_model": "mistral-medium-latest",
            "embed_model": embed_model,
        },
    )

    assert response.status_code == 200
    assert response.json()["embed_model"] == embed_model


def _mock_mistral_http(monkeypatch: pytest.MonkeyPatch, *, failing_path: str | None = None):
    requests: list[httpx.Request] = []
    real_client = httpx.Client

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == failing_path:
            return httpx.Response(404, json={"message": "Model unavailable"})
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})
        if request.url.path == "/v1/embeddings":
            return httpx.Response(200, json={"data": [{"embedding": [0.25, 0.75]}]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handle_request)

    def build_client(*, timeout: float) -> httpx.Client:
        return real_client(transport=transport, timeout=timeout)

    monkeypatch.setattr(
        mistral_client,
        "httpx",
        SimpleNamespace(Client=build_client, HTTPError=httpx.HTTPError),
    )
    return requests


def test_connection_checks_each_configured_model_and_invalidates_stale_success(
    demo_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _save_mistral_settings(demo_client, embed_model="mistral-embed")
    requests = _mock_mistral_http(monkeypatch)

    response = demo_client.post("/api/v1/settings/test")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "models": ["mistral-medium-latest", "mistral-embed"],
        "error": None,
    }
    assert [request.url.path for request in requests] == [
        "/v1/chat/completions",
        "/v1/embeddings",
    ]
    assert requests[0].headers["authorization"] == "Bearer synthetic-test-key"
    chat_payload = json.loads(requests[0].content)
    assert chat_payload["model"] == "mistral-medium-latest"
    assert chat_payload["messages"] == [{"role": "user", "content": "Reply OK."}]
    assert chat_payload["max_tokens"] == 1
    embedding_payload = json.loads(requests[1].content)
    assert embedding_payload["model"] == "mistral-embed"
    assert embedding_payload["input"] == ["Mistral connection check."]
    assert demo_client.get("/api/v1/settings").json()["llm_tested"] is True

    changed = demo_client.post("/api/v1/settings", json={"chat_model": "mistral-new-model"})
    assert changed.status_code == 200
    assert changed.json()["llm_tested"] is False


def test_connection_skips_embedding_when_model_is_blank(
    demo_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _save_mistral_settings(demo_client, embed_model="")
    requests = _mock_mistral_http(monkeypatch)

    response = demo_client.post("/api/v1/settings/test")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["models"] == ["mistral-medium-latest"]
    assert [request.url.path for request in requests] == ["/v1/chat/completions"]
    assert demo_client.get("/api/v1/settings").json()["embed_model"] == ""
    assert demo_client.get("/api/v1/settings").json()["llm_tested"] is True


@pytest.mark.parametrize(
    ("failing_path", "unavailable_model", "passed_models"),
    [
        (
            "/v1/chat/completions",
            "mistral-medium-latest",
            ["mistral-embed"],
        ),
        (
            "/v1/embeddings",
            "mistral-embed",
            ["mistral-medium-latest"],
        ),
    ],
)
def test_connection_reports_inaccessible_configured_models(
    demo_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    failing_path: str,
    unavailable_model: str,
    passed_models: list[str],
) -> None:
    _save_mistral_settings(demo_client, embed_model="mistral-embed")
    requests = _mock_mistral_http(monkeypatch, failing_path=failing_path)

    response = demo_client.post("/api/v1/settings/test")

    assert response.status_code == 200
    result = response.json()
    assert result["ok"] is False
    assert result["models"] == passed_models
    assert unavailable_model in result["error"]
    assert "404" in result["error"]
    assert [request.url.path for request in requests] == [
        "/v1/chat/completions",
        "/v1/embeddings",
    ]
    assert demo_client.get("/api/v1/settings").json()["llm_tested"] is False
