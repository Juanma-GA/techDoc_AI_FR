"""Routes /api/v1/settings — get/post + test sans clé."""

from __future__ import annotations


def test_read_settings_defaults(client) -> None:
    r = client.get("/api/v1/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["api_key_set"] is False
    assert body["base_url"].startswith("https://")
    assert body["chat_model"]
    assert body["embed_model"]


def test_write_then_read_settings(client) -> None:
    r = client.post(
        "/api/v1/settings",
        json={
            "api_key": "test-key",
            "base_url": "https://api.mistral.ai",
            "chat_model": "mistral-small-latest",
            "embed_model": "mistral-embed",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["api_key_set"] is True
    assert body["chat_model"] == "mistral-small-latest"


def test_test_connection_without_key(client) -> None:
    r = client.post("/api/v1/settings/test")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "MISTRAL_API_KEY" in (body["error"] or "")
