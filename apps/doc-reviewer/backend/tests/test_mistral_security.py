"""Mistral URL and network safety tests use synthetic configuration only."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import settings as settings_api
from app.core import llm_suggester, mistral_vision
from app.core import mistral_settings
from app.core.encryption import EncryptionError, SecretManager
from app.core.errors import AppError
from app.core.security import validate_mistral_base_url
from app.core.llm_suggester import MAX_RULE_SUGGEST_INPUT_CHARS, suggest_rules_from_corpus
from app.db.models import AppConfig
from app.db.session import SessionLocal


@pytest.mark.parametrize(
    "url",
    [
        "http://api.mistral.ai",
        "https://localhost",
        "https://127.0.0.1",
        "https://10.0.0.1",
        "https://169.254.169.254",
        "https://[::1]",
        "https://api.mistral.ai.attacker.test",
        "https://user@api.mistral.ai",
        "https://api.mistral.ai:8443",
        "https://api.mistral.ai/v1",
        "https://api.mistral.ai?next=internal",
    ],
)
def test_mistral_base_url_rejects_untrusted_targets(url: str) -> None:
    with pytest.raises(ValueError):
        validate_mistral_base_url(url)


@pytest.mark.parametrize(
    "url",
    ["https://api.mistral.ai", "https://API.MISTRAL.AI:443/"],
)
def test_mistral_base_url_normalizes_the_allowed_origin(url: str) -> None:
    assert validate_mistral_base_url(url) == "https://api.mistral.ai"


def test_settings_reject_untrusted_mistral_url(client: TestClient) -> None:
    response = client.post(
        "/api/v1/settings/mistral",
        json={"base_url": "http://127.0.0.1:8000"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "MISTRAL_URL_NOT_ALLOWED"


def test_mistral_test_does_not_follow_redirects(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    redirect_transport = httpx.MockTransport(
        lambda request: (
            requests.append(request)
            or httpx.Response(302, headers={"Location": "http://127.0.0.1/internal"})
        )
    )
    real_client = httpx.Client
    redirect_settings: list[bool] = []

    def mock_client(*, timeout: float, follow_redirects: bool) -> httpx.Client:
        redirect_settings.append(follow_redirects)
        return real_client(
            transport=redirect_transport,
            timeout=timeout,
            follow_redirects=follow_redirects,
        )

    monkeypatch.setattr(settings_api.httpx, "Client", mock_client)
    monkeypatch.setattr(settings_api, "get_llm_enabled", lambda _db: True)
    monkeypatch.setattr(
        settings_api,
        "get_effective",
        lambda _db: {
            "api_key": "synthetic-key",
            "base_url": "https://api.mistral.ai",
            "chat_model": "synthetic-model",
            "vision_model": "synthetic-model",
        },
    )
    monkeypatch.setattr(settings_api, "set_llm_tested", lambda *_args: None)

    response = client.post("/api/v1/settings/mistral/test")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert len(requests) == 1
    assert redirect_settings == [False]


@pytest.mark.parametrize(
    ("module", "call"),
    [
        (llm_suggester, lambda db: llm_suggester._call_mistral(db, "system", "user")),
        (mistral_vision, lambda db: mistral_vision._call_mistral_vision(db, [])),
    ],
)
def test_invalid_runtime_url_never_creates_http_client(
    module: object,
    call,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_client(*_args, **_kwargs):
        pytest.fail("untrusted URL reached the HTTP client")

    monkeypatch.setattr(module, "get_llm_enabled", lambda _db: True)
    monkeypatch.setattr(
        module,
        "get_effective",
        lambda _db: {
            "api_key": "synthetic-key",
            "base_url": "http://127.0.0.1:8000",
            "chat_model": "synthetic-model",
            "vision_model": "synthetic-model",
        },
    )
    monkeypatch.setattr(module.httpx, "Client", unexpected_client)

    with pytest.raises(AppError):
        call(object())


@pytest.mark.parametrize(
    ("module", "call"),
    [
        (llm_suggester, lambda db: llm_suggester._call_mistral(db, "system", "user")),
        (mistral_vision, lambda db: mistral_vision._call_mistral_vision(db, [])),
    ],
)
def test_disabled_runtime_helpers_never_create_http_client(
    module: object,
    call,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "get_llm_enabled", lambda _db: False)
    monkeypatch.setattr(
        module,
        "get_effective",
        lambda _db: {
            "api_key": "SYNTHETIC-KEY",
            "base_url": "https://api.mistral.ai",
            "chat_model": "synthetic-model",
            "vision_model": "synthetic-model",
        },
    )
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda *_args, **_kwargs: pytest.fail("disabled LLM opened an HTTP client"),
    )

    with pytest.raises(AppError) as exc_info:
        call(object())

    assert exc_info.value.code == "LLM_DISABLED"


@pytest.mark.parametrize(
    ("module", "call"),
    [
        (llm_suggester, lambda db: llm_suggester._call_mistral(db, "system", "user")),
        (mistral_vision, lambda db: mistral_vision._call_mistral_vision(db, [])),
    ],
)
def test_unconfigured_runtime_helpers_never_create_http_client(
    module: object,
    call,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "get_llm_enabled", lambda _db: True)
    monkeypatch.setattr(
        module,
        "get_effective",
        lambda _db: {
            "api_key": "",
            "base_url": "https://api.mistral.ai",
            "chat_model": "synthetic-model",
            "vision_model": "synthetic-model",
        },
    )
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda *_args, **_kwargs: pytest.fail("unconfigured LLM opened an HTTP client"),
    )

    with pytest.raises(AppError) as exc_info:
        call(object())

    assert exc_info.value.code == "MISTRAL_NOT_CONFIGURED"


def test_disabled_mistral_has_no_network_call(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_client(*_args, **_kwargs):
        pytest.fail("disabled Mistral must not create an HTTP client")

    monkeypatch.setattr(settings_api, "get_llm_enabled", lambda _db: False)
    monkeypatch.setattr(settings_api, "set_llm_tested", lambda *_args: None)
    monkeypatch.setattr(settings_api.httpx, "Client", unexpected_client)

    response = client.post("/api/v1/settings/mistral/test")

    assert response.status_code == 200
    assert response.json() == {"ok": False, "message": "LLM desactive", "models": []}


def test_missing_encryption_key_refuses_mistral_key_storage(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mistral_settings.settings, "encryption_key", "")
    db = SessionLocal()
    try:
        db.query(AppConfig).filter(AppConfig.key == "mistral.api_key").delete()
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/settings/mistral",
        json={"api_key": "SYNTHETIC-KEY-MUST-NOT-PERSIST"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "MISTRAL_KEY_ENCRYPTION_REQUIRED"
    db = SessionLocal()
    try:
        assert db.get(AppConfig, "mistral.api_key") is None
    finally:
        db.close()


def test_secret_manager_without_key_refuses_plaintext_round_trip() -> None:
    manager = SecretManager(None)

    with pytest.raises(EncryptionError):
        manager.encrypt("SYNTHETIC-SECRET")


def test_rule_suggestions_disabled_are_explicit_and_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm_suggester, "get_llm_enabled", lambda _db: False)
    monkeypatch.setattr(
        llm_suggester,
        "_call_mistral",
        lambda *_args, **_kwargs: pytest.fail("disabled LLM reached the HTTP call"),
    )

    with pytest.raises(AppError) as exc_info:
        suggest_rules_from_corpus(object(), ["SYNTHETIC-CONTENT"])

    assert exc_info.value.code == "LLM_DISABLED"


def test_oversized_rule_corpus_is_rejected_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm_suggester, "get_llm_enabled", lambda _db: True)
    monkeypatch.setattr(
        llm_suggester,
        "_call_mistral",
        lambda *_args, **_kwargs: pytest.fail("oversized corpus reached the HTTP call"),
    )

    with pytest.raises(AppError) as exc_info:
        suggest_rules_from_corpus(
            object(),
            ["SYNTHETIC-CONTENT" * MAX_RULE_SUGGEST_INPUT_CHARS],
        )

    assert exc_info.value.code == "RULE_SUGGEST_INPUT_TOO_LARGE"


def test_rule_suggestions_do_not_truncate_valid_results(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    items = [
        {
            "name": f"Synthetic rule {index}",
            "kind": "term_replace",
            "pattern": f"term-{index}",
            "replacement": "replacement",
            "severity": "warning",
            "message": "Synthetic suggestion",
        }
        for index in range(13)
    ]
    monkeypatch.setattr(llm_suggester, "get_llm_enabled", lambda _db: True)
    monkeypatch.setattr(
        llm_suggester,
        "_call_mistral",
        lambda *_args, **_kwargs: json.dumps({"rules": items}),
    )

    suggestions = suggest_rules_from_corpus(object(), ["SYNTHETIC-CONTENT"])

    assert len(suggestions) == 13