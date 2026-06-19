"""GET /api/v1/health smoke test + etat LLM 4-positions (badge ON conditionnel)."""

from __future__ import annotations

import pytest


def test_health_ok(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "db" in body
    assert "llm" in body


@pytest.fixture
def db_session():
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _clear_llm_config(db) -> None:
    """Remet l'etat LLM par defaut (cle vide, jamais teste) pour isoler le test."""
    from app.core.mistral_client import CONFIG_KEYS, LLM_TESTED_KEY, _write_config

    _write_config(db, CONFIG_KEYS["api_key"], "")
    _write_config(db, LLM_TESTED_KEY, "false")
    db.commit()


def test_health_llm_untested_when_key_present_but_not_tested(client, db_session) -> None:
    from app.core.mistral_client import CONFIG_KEYS, _write_config

    _clear_llm_config(db_session)
    _write_config(db_session, CONFIG_KEYS["api_key"], "sk-test-key")
    db_session.commit()
    try:
        body = client.get("/api/v1/health").json()
        assert body["llm"] == "untested"
    finally:
        _clear_llm_config(db_session)


def test_health_llm_ok_after_set_llm_tested(client, db_session) -> None:
    from app.core.mistral_client import CONFIG_KEYS, _write_config, set_llm_tested

    _clear_llm_config(db_session)
    _write_config(db_session, CONFIG_KEYS["api_key"], "sk-test-key")
    db_session.commit()
    set_llm_tested(db_session, True)
    try:
        body = client.get("/api/v1/health").json()
        assert body["llm"] == "ok"
    finally:
        _clear_llm_config(db_session)


def test_health_llm_not_configured_without_key(client, db_session) -> None:
    _clear_llm_config(db_session)
    try:
        body = client.get("/api/v1/health").json()
        assert body["llm"] == "not_configured"
    finally:
        _clear_llm_config(db_session)


def test_save_settings_new_api_key_resets_tested_flag(db_session) -> None:
    from app.core.mistral_client import get_llm_tested, save_settings, set_llm_tested

    _clear_llm_config(db_session)
    save_settings(db_session, {"api_key": "sk-first"})
    set_llm_tested(db_session, True)
    assert get_llm_tested(db_session) is True

    # Ecrire une nouvelle cle doit invalider le dernier test reussi.
    save_settings(db_session, {"api_key": "sk-second"})
    try:
        assert get_llm_tested(db_session) is False
    finally:
        _clear_llm_config(db_session)
