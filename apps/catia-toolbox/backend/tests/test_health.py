"""GET /api/v1/health smoke test + logique du badge LLM (4 etats)."""

from __future__ import annotations


def _llm(client) -> str:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    return r.json()["llm"]


def test_health_ok(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "db" in body
    assert "llm" in body


def test_health_untested_when_key_present_but_not_tested(client) -> None:
    """Cle configuree + LLM actif + jamais teste => 'untested' (badge A TESTER)."""
    from app.core.mistral_client import save_settings
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-test-123"})
    finally:
        db.close()

    assert _llm(client) == "untested"


def test_health_ok_after_set_llm_tested(client) -> None:
    """Cle + LLM actif + dernier test reussi => 'ok' (badge ON)."""
    from app.core.mistral_client import save_settings, set_llm_tested
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-test-123"})
        set_llm_tested(db, True)
    finally:
        db.close()

    assert _llm(client) == "ok"


def test_save_settings_new_api_key_resets_tested_flag(client) -> None:
    """Changer la cle invalide le dernier test reussi => retour a 'untested'."""
    from app.core.mistral_client import get_llm_tested, save_settings, set_llm_tested
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-test-123"})
        set_llm_tested(db, True)
        assert get_llm_tested(db) is True

        # Nouvelle cle => le flag doit retomber a False.
        save_settings(db, {"api_key": "sk-test-456"})
        assert get_llm_tested(db) is False
    finally:
        db.close()

    assert _llm(client) == "untested"
