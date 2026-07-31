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


# ---------------------------------------------------------------------------
# La dictee vocale utilise bien la cle/URL DEDIEES Voxtral (config Parametres).
# On intercepte l'appel httpx reel (pas de stub de transcribe_audio) pour
# verifier l'URL et le header Authorization effectivement envoyes au micro.
# ---------------------------------------------------------------------------


def _configure(settings: dict) -> None:
    """Persiste une config Mistral/Voxtral arbitraire, LLM active."""
    db = SessionLocal()
    try:
        save_settings(db, settings)
        set_llm_enabled(db, True)
    finally:
        db.close()


class _FakeResponse:
    """Reponse httpx minimale pour /v1/audio/transcriptions."""

    def __init__(self, text: str) -> None:
        self._text = text

    def raise_for_status(self) -> None:  # pragma: no cover - no-op
        return None

    def json(self) -> dict:
        return {"text": self._text}


def _capture_post(monkeypatch: pytest.MonkeyPatch, reply: str = "texte dicte") -> dict:
    """Remplace httpx.Client.post et enregistre l'URL + les headers de l'appel.

    TestClient est lui-meme un httpx.Client : on ne detourne QUE l'appel
    transcription, le reste (requetes ASGI du TestClient) passe a l'original."""
    import httpx

    captured: dict = {}
    real_post = httpx.Client.post

    def _fake_post(self, url, *, headers=None, files=None, data=None, **kw):  # type: ignore[no-untyped-def]
        if str(url).endswith("/v1/audio/transcriptions"):
            captured["url"] = str(url)
            captured["headers"] = headers or {}
            captured["model"] = (data or {}).get("model")
            return _FakeResponse(reply)
        return real_post(self, url, headers=headers, files=files, data=data, **kw)

    monkeypatch.setattr(httpx.Client, "post", _fake_post)
    return captured


def test_transcribe_uses_dedicated_voxtral_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cle Voxtral dediee renseignee -> l'appel part sur son URL avec sa cle."""
    _configure(
        {
            "api_key": "sk-main-key",
            "base_url": "https://api.mistral.ai",
            "voxtral_api_key": "vx-dedicated-key",
            "voxtral_base_url": "https://voxtral.example.com",
            "transcribe_model": "voxtral-mini-transcribe-26-02",
        }
    )
    captured = _capture_post(monkeypatch, reply="Compte-rendu dicte.")

    resp = client.post("/api/v1/sessions/transcribe", files={"file": AUDIO})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"text": "Compte-rendu dicte.", "llm_used": True}
    # URL + cle = valeurs DEDIEES (pas la cle Mistral principale).
    assert captured["url"] == "https://voxtral.example.com/v1/audio/transcriptions"
    assert captured["headers"]["Authorization"] == "Bearer vx-dedicated-key"
    assert captured["model"] == "voxtral-mini-transcribe-26-02"


def test_transcribe_falls_back_to_main_key_without_dedicated(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sans cle Voxtral dediee -> l'appel repli sur la cle/URL Mistral principale."""
    _configure({"api_key": "sk-main-key", "base_url": "https://api.mistral.ai"})
    captured = _capture_post(monkeypatch)

    resp = client.post("/api/v1/sessions/transcribe", files={"file": AUDIO})
    assert resp.status_code == 200, resp.text
    assert captured["url"] == "https://api.mistral.ai/v1/audio/transcriptions"
    assert captured["headers"]["Authorization"] == "Bearer sk-main-key"
