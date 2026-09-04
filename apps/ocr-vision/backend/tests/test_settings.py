"""Routes /api/v1/settings — badge LLM : vert (ON) seulement si cle + LLM
active + dernier test reussi."""

from __future__ import annotations


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
