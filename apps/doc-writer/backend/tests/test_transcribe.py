"""Dictee vocale Voxtral : endpoints /sessions/transcribe + methode client.

Aucun appel reseau reel : les appels `MistralClient` sont doubles.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.core.mistral_client import save_settings, set_llm_enabled
from app.db.session import SessionLocal

AUDIO = ("dictation.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm")
REALTIME_MODEL = "voxtral-mini-transcribe-realtime-2602"


def _configure_llm(enabled: bool = True) -> None:
    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-test-1234567890"})
        set_llm_enabled(db, enabled)
    finally:
        db.close()


def test_realtime_token_returns_short_lived_session(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _create(self):  # type: ignore[no-untyped-def]
        return "rt_test_token"

    _configure_llm(True)
    monkeypatch.setattr(
        "app.core.mistral_client.MistralClient.create_realtime_token",
        _create,
    )

    response = client.post("/api/v1/sessions/transcribe/realtime-token")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "enabled": True,
        "token": "rt_test_token",
        "model": REALTIME_MODEL,
        "websocket_url": (
            "wss://api.mistral.ai/v1/audio/transcriptions/realtime"
            f"?model={REALTIME_MODEL}"
        ),
    }


def test_realtime_token_is_graceful_when_llm_disabled(client: TestClient) -> None:
    _configure_llm(False)

    response = client.post("/api/v1/sessions/transcribe/realtime-token")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "token": "",
        "model": REALTIME_MODEL,
        "websocket_url": "",
    }


@pytest.mark.asyncio
async def test_create_realtime_token_uses_dedicated_voxtral_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    captured: dict = {}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"client_secret": {"value": "rt_dedicated"}}

    async def _post(self, url, **kwargs):  # type: ignore[no-untyped-def]
        captured.update(url=str(url), **kwargs)
        return _Response()

    monkeypatch.setattr(httpx.AsyncClient, "post", _post)
    from app.core.mistral_client import MistralClient

    mistral = MistralClient(
        api_key="sk-main",
        base_url="https://api.mistral.ai",
        chat_model="mistral-small-latest",
        embed_model="mistral-embed",
        transcribe_api_key="vx-dedicated",
        transcribe_base_url="https://voxtral.example.com",
    )

    token = await mistral.create_realtime_token()

    assert token == "rt_dedicated"
    assert captured["url"] == "https://voxtral.example.com/v1/client/sessions"
    assert captured["headers"]["Authorization"] == "Bearer vx-dedicated"
    assert captured["json"] == {"purpose": "realtime", "model": REALTIME_MODEL}


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


def test_transcribe_stream_relays_deltas(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _stream(self, audio, filename="d.webm", **kw) -> AsyncIterator[str]:  # type: ignore[no-untyped-def]
        yield "Le client "
        yield "est ACME."

    _configure_llm(True)
    monkeypatch.setattr(
        "app.core.mistral_client.MistralClient.transcribe_audio_stream",
        _stream,
    )

    resp = client.post("/api/v1/sessions/transcribe/stream", files={"file": AUDIO})

    assert resp.status_code == 200, resp.text
    assert "event: token\r\ndata: Le client " in resp.text
    assert "event: token\r\ndata: est ACME." in resp.text
    assert 'event: done\r\ndata: {"llm_used": true}' in resp.text


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
            "transcribe_model": "voxtral-mini-latest",
        }
    )
    captured = _capture_post(monkeypatch, reply="Compte-rendu dicte.")

    resp = client.post("/api/v1/sessions/transcribe", files={"file": AUDIO})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"text": "Compte-rendu dicte.", "llm_used": True}
    # URL + cle = valeurs DEDIEES (pas la cle Mistral principale).
    assert captured["url"] == "https://voxtral.example.com/v1/audio/transcriptions"
    assert captured["headers"]["Authorization"] == "Bearer vx-dedicated-key"
    assert captured["model"] == "voxtral-mini-latest"


def test_realtime_model_is_replaced_for_file_transcription() -> None:
    from app.core.mistral_client import MistralClient

    _configure(
        {
            "api_key": "sk-test",
            "transcribe_model": "voxtral-mini-transcribe-realtime-2602",
        }
    )
    db = SessionLocal()
    try:
        mistral = MistralClient.from_db(db)
    finally:
        db.close()

    assert mistral.transcribe_model == "voxtral-mini-latest"


def test_transcribe_falls_back_to_main_key_without_dedicated(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sans cle Voxtral dediee -> l'appel repli sur la cle/URL Mistral principale."""
    from app.config import settings

    monkeypatch.setattr(settings, "voxtral_api_key", "")
    monkeypatch.setattr(settings, "voxtral_base_url", "")
    _configure(
        {
            "api_key": "sk-main-key",
            "base_url": "https://api.mistral.ai",
            "voxtral_api_key": "",
            "voxtral_base_url": "",
        }
    )
    captured = _capture_post(monkeypatch)

    resp = client.post("/api/v1/sessions/transcribe", files={"file": AUDIO})
    assert resp.status_code == 200, resp.text
    assert captured["url"] == "https://api.mistral.ai/v1/audio/transcriptions"
    assert captured["headers"]["Authorization"] == "Bearer sk-main-key"


@pytest.mark.asyncio
async def test_transcribe_stream_enables_mistral_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    captured: dict = {}

    class _StreamResponse:
        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):  # type: ignore[no-untyped-def]
            yield 'data: {"type":"transcription.text.delta","text":"Bonjour"}'
            yield ""
            yield "data: [DONE]"

    class _StreamContext:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return _StreamResponse()

        async def __aexit__(self, *args):  # type: ignore[no-untyped-def]
            return None

    def _fake_stream(self, method, url, **kwargs):  # type: ignore[no-untyped-def]
        captured.update(method=method, url=url, **kwargs)
        return _StreamContext()

    monkeypatch.setattr(httpx.AsyncClient, "stream", _fake_stream)
    from app.core.mistral_client import MistralClient

    mistral = MistralClient(
        api_key="sk-test",
        base_url="https://api.mistral.ai",
        chat_model="mistral-small-latest",
        embed_model="mistral-embed",
    )
    deltas = [delta async for delta in mistral.transcribe_audio_stream(b"audio")]

    assert deltas == ["Bonjour"]
    assert captured["data"]["stream"] == "true"
    assert captured["data"]["model"] == "voxtral-mini-latest"
