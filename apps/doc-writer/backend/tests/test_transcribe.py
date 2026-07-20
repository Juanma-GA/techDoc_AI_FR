"""Dictee vocale Voxtral : endpoint /sessions/transcribe + methode client.

Aucun appel reseau reel : on stub `MistralClient.transcribe_audio`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.mistral_client import save_settings, set_llm_enabled
from app.db.session import SessionLocal

AUDIO = ("dictation.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm")


def _configure_llm(enabled: bool = True) -> None:
    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-test-1234567890"})
        set_llm_enabled(db, enabled)
    finally:
        db.close()


def test_transcribe_returns_text(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_llm(True)
    monkeypatch.setattr(
        "app.core.mistral_client.MistralClient.transcribe_audio",
        lambda self, audio, filename="d.webm", **kw: "Le client est ACME, priorite haute.",
    )
    resp = client.post("/api/v1/sessions/transcribe", files={"file": AUDIO})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["llm_used"] is True
    assert body["text"] == "Le client est ACME, priorite haute."


def test_transcribe_graceful_when_llm_disabled(client: TestClient) -> None:
    """LLM OFF → 200 + texte vide (jamais 5xx, regle #6)."""
    _configure_llm(False)
    resp = client.post("/api/v1/sessions/transcribe", files={"file": AUDIO})
    assert resp.status_code == 200
    assert resp.json() == {"text": "", "llm_used": False}


def test_transcribe_rejects_non_audio(client: TestClient) -> None:
    _configure_llm(True)
    resp = client.post(
        "/api/v1/sessions/transcribe",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


def test_transcribe_rejects_empty_audio(client: TestClient) -> None:
    _configure_llm(True)
    resp = client.post(
        "/api/v1/sessions/transcribe",
        files={"file": ("d.webm", b"", "audio/webm")},
    )
    assert resp.status_code == 400


def test_transcribe_surfaces_mistral_http_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un 4xx/5xx de l'API doit remonter le code + le corps (diagnostic)."""
    import httpx

    def _raise(self, audio, filename="d.webm", **kw):  # type: ignore[no-untyped-def]
        request = httpx.Request("POST", "https://api.mistral.ai/v1/audio/transcriptions")
        response = httpx.Response(404, text='{"message":"model not found"}', request=request)
        raise httpx.HTTPStatusError("404", request=request, response=response)

    _configure_llm(True)
    monkeypatch.setattr("app.core.mistral_client.MistralClient.transcribe_audio", _raise)
    resp = client.post("/api/v1/sessions/transcribe", files={"file": AUDIO})
    assert resp.status_code == 502
    body = resp.json()
    # Modele invalide/indisponible -> message explicite oriente Parametres.
    assert "Parametres" in body["message"]
    assert body["detail"]["status"] == 404
