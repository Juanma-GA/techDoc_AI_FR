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


def test_default_fill_prompt_has_content_adaptation_clause(client) -> None:
    """Le prompt de remplissage par defaut porte la clause d'adaptation au
    contenu pour les zones a `instruction` (assouplissement de la pertinence)."""
    r = client.get("/api/v1/settings/prompts")
    assert r.status_code == 200, r.text
    fill = r.json()["pptx_fill"]
    assert fill["is_default"] is True
    val = fill["value"]
    assert "instruction" in val
    assert "ADAPTE-TOI au contenu" in val


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


# ---------------------------------------------------------------------------
# Cle/URL DEDIEES a la transcription Voxtral (volet Parametres) + cablage.
# ---------------------------------------------------------------------------


def test_voxtral_config_absent_by_default(client) -> None:
    r = client.get("/api/v1/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["voxtral_api_key_set"] is False
    assert body["voxtral_base_url"] == ""


def test_write_voxtral_dedicated_key_roundtrip(client) -> None:
    r = client.post(
        "/api/v1/settings",
        json={
            "voxtral_api_key": "vx-secret-key",
            "voxtral_base_url": "https://voxtral.example.com",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Le secret n'est jamais renvoye, seul le flag "set" + l'URL en clair.
    assert body["voxtral_api_key_set"] is True
    assert body["voxtral_base_url"] == "https://voxtral.example.com"
    assert "vx-secret-key" not in r.text


def test_voxtral_key_does_not_reset_llm_tested(client) -> None:
    """Changer la cle Voxtral n'invalide PAS le dernier test Mistral (seule la
    cle/URL principale le fait)."""
    from app.core.mistral_client import LLM_TESTED_KEY, get_llm_tested
    from app.db.session import SessionLocal

    _set_config(LLM_TESTED_KEY, "true")
    r = client.post("/api/v1/settings", json={"voxtral_api_key": "vx-key"})
    assert r.status_code == 200
    assert r.json()["llm_tested"] is True
    db = SessionLocal()
    try:
        assert get_llm_tested(db) is True
    finally:
        db.close()


def test_transcribe_client_falls_back_to_main_key_without_dedicated() -> None:
    from app.core.mistral_client import MistralClient, save_settings
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-main", "base_url": "https://api.mistral.ai"})
        c = MistralClient.from_db(db)
    finally:
        db.close()
    assert c.transcribe_api_key == "sk-main"
    assert c.transcribe_base_url == "https://api.mistral.ai"
    assert c.transcribe_dedicated is False


def test_transcribe_client_uses_dedicated_voxtral_key() -> None:
    from app.core.mistral_client import MistralClient, save_settings
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        save_settings(
            db,
            {
                "api_key": "sk-main",
                "base_url": "https://api.mistral.ai",
                "voxtral_api_key": "vx-dedicated",
                "voxtral_base_url": "https://voxtral.example.com",
            },
        )
        c = MistralClient.from_db(db)
    finally:
        db.close()
    assert c.transcribe_api_key == "vx-dedicated"
    assert c.transcribe_base_url == "https://voxtral.example.com"
    assert c.transcribe_dedicated is True
    # Le reste (chat/embed/vision) reste sur la cle/URL principale.
    assert c.api_key == "sk-main"
    assert c.base_url == "https://api.mistral.ai"


# ---------------------------------------------------------------------------
# /settings/test : un test + une LISTE de modeles PAR API appelee.
# On stub list_models / list_transcribe_models (aucun appel reseau reel).
# ---------------------------------------------------------------------------


def test_test_lists_only_main_api_without_dedicated_voxtral(client, monkeypatch) -> None:
    from app.core.mistral_client import MistralClient

    _set_config("MISTRAL_API_KEY", "sk-main")
    monkeypatch.setattr(
        MistralClient, "list_models", lambda self: ["mistral-small-latest", "mistral-embed"]
    )

    r = client.post("/api/v1/settings/test")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    # Une seule API testee : Mistral principale (pas de cle Voxtral dediee).
    assert [a["api"] for a in body["apis"]] == ["mistral"]
    assert body["apis"][0]["ok"] is True
    assert body["apis"][0]["models"] == ["mistral-small-latest", "mistral-embed"]


def test_test_lists_both_apis_with_dedicated_voxtral(client, monkeypatch) -> None:
    from app.core.mistral_client import MistralClient

    _set_config("MISTRAL_API_KEY", "sk-main")
    _set_config("VOXTRAL_BASE_URL", "https://voxtral.example.com")
    # Cle Voxtral dediee -> passe par le chiffrement/ecriture standard.
    client.post("/api/v1/settings", json={"voxtral_api_key": "vx-dedicated"})
    monkeypatch.setattr(MistralClient, "list_models", lambda self: ["mistral-small-latest"])
    monkeypatch.setattr(
        MistralClient, "list_transcribe_models", lambda self: ["voxtral-mini-transcribe-26-02"]
    )

    r = client.post("/api/v1/settings/test")
    assert r.status_code == 200, r.text
    body = r.json()
    apis = {a["api"]: a for a in body["apis"]}
    assert set(apis) == {"mistral", "voxtral"}
    assert apis["mistral"]["models"] == ["mistral-small-latest"]
    assert apis["voxtral"]["ok"] is True
    assert apis["voxtral"]["base_url"] == "https://voxtral.example.com"
    assert apis["voxtral"]["models"] == ["voxtral-mini-transcribe-26-02"]


def test_test_voxtral_failure_does_not_break_main_badge(client, monkeypatch) -> None:
    """Voxtral KO -> son entree est ok=False, mais l'API principale reste OK et
    le badge (llm_tested) n'est PAS invalide."""
    from app.core.mistral_client import MistralClient, get_llm_tested
    from app.db.session import SessionLocal

    _set_config("MISTRAL_API_KEY", "sk-main")
    client.post("/api/v1/settings", json={"voxtral_api_key": "vx-dedicated"})

    def _boom(self):  # type: ignore[no-untyped-def]
        raise RuntimeError("voxtral down")

    monkeypatch.setattr(MistralClient, "list_models", lambda self: ["mistral-small-latest"])
    monkeypatch.setattr(MistralClient, "list_transcribe_models", _boom)

    r = client.post("/api/v1/settings/test")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True  # API principale OK -> badge vert possible.
    apis = {a["api"]: a for a in body["apis"]}
    assert apis["voxtral"]["ok"] is False
    assert "voxtral down" in (apis["voxtral"]["error"] or "")
    db = SessionLocal()
    try:
        assert get_llm_tested(db) is True
    finally:
        db.close()
