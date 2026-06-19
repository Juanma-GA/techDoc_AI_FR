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


# ---------------------------------------------------------------------------
# Badge LLM : vert (ON) seulement si cle + LLM active + dernier test reussi.
# ---------------------------------------------------------------------------


def _set_config(key: str, value: str) -> None:
    from app.db import models
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(models.AppConfig, key)
        if row is None:
            db.add(models.AppConfig(key=key, value=value))
        else:
            row.value = value
        db.commit()
    finally:
        db.close()


def test_health_untested_when_key_set_but_not_tested(client) -> None:
    # Cle presente mais aucun test reussi enregistre -> "untested".
    _set_config("MISTRAL_API_KEY", "test-key")
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["llm"] == "untested"


def test_health_ok_after_set_llm_tested(client) -> None:
    from app.core.mistral_client import set_llm_tested
    from app.db.session import SessionLocal

    _set_config("MISTRAL_API_KEY", "test-key")
    db = SessionLocal()
    try:
        set_llm_tested(db, True)
    finally:
        db.close()
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["llm"] == "ok"


def test_save_settings_resets_llm_tested(client) -> None:
    from app.core.mistral_client import LLM_TESTED_KEY, get_llm_tested
    from app.db.session import SessionLocal

    # On marque un test reussi, puis on enregistre une nouvelle cle.
    _set_config(LLM_TESTED_KEY, "true")
    r = client.post("/api/v1/settings", json={"api_key": "another-key"})
    assert r.status_code == 200
    assert r.json()["llm_tested"] is False
    db = SessionLocal()
    try:
        assert get_llm_tested(db) is False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Prompts LLM editables runtime (/settings/prompts).
# ---------------------------------------------------------------------------


def test_read_prompts_defaults(client) -> None:
    r = client.get("/api/v1/settings/prompts")
    assert r.status_code == 200, r.text
    body = r.json()
    # Les deux prompts sont au defaut tant qu'aucune valeur n'est persistee.
    assert body["pptx_analysis"]["is_default"] is True
    assert body["pptx_fill"]["is_default"] is True
    assert body["pptx_analysis"]["value"]


def test_write_then_reset_prompt(client) -> None:
    # Ecrit une valeur custom pour pptx_fill.
    r = client.post(
        "/api/v1/settings/prompts",
        json={"pptx_fill": "Mon prompt custom de remplissage."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pptx_fill"]["is_default"] is False
    assert body["pptx_fill"]["value"] == "Mon prompt custom de remplissage."
    # pptx_analysis non touche (None ignore) -> reste au defaut.
    assert body["pptx_analysis"]["is_default"] is True

    # Chaine vide = reset au defaut.
    r2 = client.post("/api/v1/settings/prompts", json={"pptx_fill": ""})
    assert r2.status_code == 200, r2.text
    assert r2.json()["pptx_fill"]["is_default"] is True
