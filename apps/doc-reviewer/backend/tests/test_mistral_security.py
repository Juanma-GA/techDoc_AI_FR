"""Mistral URL and network safety tests use synthetic configuration only."""

from typing import cast

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import settings as settings_api
from app.core import llm_suggester, mistral_vision
from app.core import mistral_settings
from app.core.encryption import EncryptionError, SecretManager
from app.core.errors import AppError
from app.core.llm_suggester import MAX_RULE_SUGGEST_INPUT_CHARS, suggest_rules_from_corpus
from app.db.models import AppConfig
from app.db.session import SessionLocal


# NB: the base_url allowlist itself (SSRF/key-exfiltration via private IPs,
# the loopback metadata endpoint, lookalike domains, etc.) now lives in
# `mistral_settings.validate_base_url` / `get_endpoint` — a strict exact-match
# allowlist against `MISTRAL_ALLOWED_BASE_URLS`, which structurally can't
# suffer the regex-bypass risk the old `security.validate_mistral_base_url`
# guarded against (no pattern matching at all, just string equality after
# normalization). See `test_mistral_endpoint_allowlist.py` for that coverage.


def test_settings_reject_untrusted_mistral_url(client: TestClient) -> None:
    response = client.post(
        "/api/v1/settings/mistral",
        json={"base_url": "http://127.0.0.1:8000"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "MISTRAL_BASE_URL_NOT_ALLOWED"


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
    synthetic_settings = {
        "api_key": "synthetic-key",
        "base_url": "https://api.mistral.ai",
        "chat_model": "synthetic-model",
        "vision_model": "synthetic-model",
    }
    monkeypatch.setattr(settings_api, "get_effective", lambda _db: synthetic_settings)
    monkeypatch.setattr(settings_api, "get_endpoint", lambda _db: synthetic_settings)
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
        mistral_settings,
        "get_effective",
        lambda _db: {
            "api_key": "synthetic-key",
            "base_url": "http://127.0.0.1:8000",
            "chat_model": "synthetic-model",
            "vision_model": "synthetic-model",
        },
    )
    monkeypatch.setattr(module.httpx, "Client", unexpected_client)

    with pytest.raises(AppError) as exc_info:
        call(object())

    # L-10: a rejected base_url must surface the same code/status everywhere,
    # not LLM_REPHRASE_FAILED/VISION_CALL_FAILED/502 behind a bare "ValueError"
    # that hides the real (policy) cause. `get_endpoint` raises AppError
    # directly (no ValueError indirection), so this must propagate unchanged.
    assert exc_info.value.code == "MISTRAL_BASE_URL_NOT_ALLOWED"
    assert exc_info.value.status_code == 422


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
        mistral_settings,
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


def test_unreadable_stored_key_is_reported_not_silently_hidden(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H-03 hardening: a key saved under one ENCRYPTION_KEY (or a legacy
    plaintext value from before encryption was mandatory) that can no
    longer be decrypted used to disappear silently -- `api_key_set` false,
    nothing in the API response, only a backend log line. The UI must be
    able to tell this apart from "no key was ever configured"."""
    from app.core.encryption import generate_key

    monkeypatch.setattr(mistral_settings.settings, "encryption_key", generate_key())
    db = SessionLocal()
    try:
        db.merge(AppConfig(key="mistral.api_key", value="not-a-valid-fernet-token"))
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/settings/mistral")

    assert response.status_code == 200
    body = response.json()
    assert body["api_key_set"] is False
    assert body["api_key_unreadable"] is True

    db = SessionLocal()
    try:
        db.query(AppConfig).filter(AppConfig.key == "mistral.api_key").delete()
        db.commit()
    finally:
        db.close()


def test_secret_manager_without_key_refuses_plaintext_round_trip() -> None:
    manager = SecretManager(None)

    with pytest.raises(EncryptionError):
        manager.encrypt("SYNTHETIC-SECRET")


def test_mistral_setting_without_encryption_key_logs_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # structlog here is configured with `PrintLoggerFactory` (writes straight
    # to stdout, bypassing stdlib `logging`) — `caplog` sees nothing, same as
    # every other structlog assertion in this backend (see test_logging.py).
    monkeypatch.setattr(mistral_settings.settings, "encryption_key", "")

    class StoredSetting:
        value = "encrypted-value"

    class StoredSettings:
        def get(self, _model: object, _key: str) -> StoredSetting:
            return StoredSetting()

    assert mistral_settings._get(cast(Session, StoredSettings()), "api_key") is None
    output = capsys.readouterr().out
    assert "Failed to decrypt Mistral setting" in output
    assert "api_key" in output


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