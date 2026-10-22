"""Mistral : la cle API et le texte des documents ne partent jamais vers une
URL hors liste blanche (exfiltration de cle / SSRF via base_url)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from cryptography.fernet import Fernet

from app.config import settings
from app.core.errors import AppError
from app.db.models import AppConfig
from app.db.session import SessionLocal


# ---------------------------------------------------------------------------
# Mistral : pas d'exfiltration de la cle / SSRF via base_url
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _configure_test_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode("ascii"))


@pytest.fixture
def clean_mistral_config():
    def _clean() -> None:
        db = SessionLocal()
        try:
            db.execute(delete(AppConfig).where(AppConfig.key.like("mistral.%")))
            db.commit()
        finally:
            db.close()

    _clean()
    yield
    _clean()


def _store_raw(key: str, value: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(AppConfig, key)
        if row is None:
            db.add(AppConfig(key=key, value=value))
        else:
            row.value = value
        db.commit()
    finally:
        db.close()


def test_base_url_outside_allowlist_is_rejected(client: TestClient, clean_mistral_config: None) -> None:
    client.post("/api/v1/settings/mistral", json={"api_key": "sk-real-key-0123456789"})
    response = client.post("/api/v1/settings/mistral", json={"base_url": "https://attacker.example"})
    assert response.status_code == 422
    assert response.json()["code"] == "MISTRAL_BASE_URL_NOT_ALLOWED"
    assert client.get("/api/v1/settings/mistral").json()["base_url"] == "https://api.mistral.ai"

    for bad in (
        "http://api.mistral.ai",
        "https://user:pw@api.mistral.ai",
        "https://api.mistral.ai/?x=1",
        "file:///etc/passwd",
    ):
        response = client.post(
            "/api/v1/settings/mistral", json={"base_url": bad, "api_key": "sk-new-key-0123456789"}
        )
        assert response.status_code == 422, bad


def test_private_mistral_endpoint_is_allowed_and_ocr_model_persists(
    client: TestClient,
    clean_mistral_config: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_url = "https://api.2a91ec1812a1.dc.mistral.ai"
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode("ascii"))

    response = client.post(
        "/api/v1/settings/mistral",
        json={
            "api_key": "SYNTHETIC-MISTRAL-KEY",
            "base_url": private_url,
            "ocr_model": "mistral-ocr-private",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["base_url"] == private_url
    assert response.json()["ocr_model"] == "mistral-ocr-private"
    assert client.get("/api/v1/settings/mistral").json()["ocr_model"] == "mistral-ocr-private"


def test_changing_base_url_requires_reentering_the_key(
    client: TestClient, clean_mistral_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        settings,
        "mistral_allowed_base_urls",
        ["https://api.mistral.ai", "https://llm.internal.example"],
    )
    client.post("/api/v1/settings/mistral", json={"api_key": "sk-real-key-0123456789"})
    response = client.post(
        "/api/v1/settings/mistral", json={"base_url": "https://llm.internal.example"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "MISTRAL_KEY_REQUIRED"

    # Meme URL (normalisee) : pas de ressaisie exigee.
    same = client.post("/api/v1/settings/mistral", json={"base_url": "https://API.mistral.ai/"})
    assert same.status_code == 200

    moved = client.post(
        "/api/v1/settings/mistral",
        json={"base_url": "https://llm.internal.example", "api_key": "sk-internal-key-0123"},
    )
    assert moved.status_code == 200
    assert moved.json()["base_url"] == "https://llm.internal.example"


def test_connection_test_never_sends_key_to_stored_foreign_url(
    client: TestClient, clean_mistral_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Une base_url deja en base (posee avant ce correctif) est revalidee."""
    from app.api import settings as settings_api
    from app.core import mistral_settings

    db = SessionLocal()
    try:
        mistral_settings.set_llm_enabled(db, True)
        mistral_settings.save(db, {"api_key": "sk-real-key-0123456789"})
    finally:
        db.close()
    _store_raw("mistral.base_url", "https://attacker.example")

    def _no_http(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("aucune requete HTTP ne doit partir")

    monkeypatch.setattr(settings_api.httpx, "Client", _no_http)
    body = client.post("/api/v1/settings/mistral/test").json()
    assert body["ok"] is False
    assert "non autorisee" in body["message"]


def test_llm_call_refuses_stored_foreign_url(
    clean_mistral_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import llm_suggester, mistral_settings, mistral_vision

    db = SessionLocal()
    try:
        mistral_settings.set_llm_enabled(db, True)
        mistral_settings.save(db, {"api_key": "sk-real-key-0123456789"})
    finally:
        db.close()
    _store_raw("mistral.base_url", "https://attacker.example")

    def _no_http(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("aucune requete HTTP ne doit partir")

    monkeypatch.setattr(llm_suggester.httpx, "Client", _no_http)
    monkeypatch.setattr(mistral_vision.httpx, "Client", _no_http)
    db = SessionLocal()
    try:
        with pytest.raises(AppError) as excinfo:
            llm_suggester.call_chat(db, "system", "texte du document")
        assert excinfo.value.code == "MISTRAL_BASE_URL_NOT_ALLOWED"
    finally:
        db.close()
