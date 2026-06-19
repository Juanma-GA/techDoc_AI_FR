"""Badge LLM vert (ON) seulement si cle + test reussi + LLM active.

Couvre l'etat health "untested" (cle presente mais jamais testee), le passage
a "ok" apres set_llm_tested(db, True), et l'invalidation du flag quand on
enregistre une nouvelle cle Mistral via save_settings.
"""

from __future__ import annotations


def _set_key(db, key: str = "sk-test") -> None:
    from app.core.mistral_client import save_settings

    save_settings(db, {"api_key": key})


def test_health_untested_when_key_present_but_not_tested(client) -> None:
    from app.core.mistral_client import save_settings, set_llm_tested
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-test"})
        set_llm_tested(db, False)
    finally:
        db.close()

    body = client.get("/api/v1/health").json()
    assert body["llm"] == "untested"


def test_health_ok_after_set_llm_tested_true(client) -> None:
    from app.core.mistral_client import save_settings, set_llm_tested
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-test"})
        set_llm_tested(db, True)
    finally:
        db.close()

    body = client.get("/api/v1/health").json()
    assert body["llm"] == "ok"


def test_save_settings_new_api_key_resets_tested_flag(client) -> None:
    from app.core.mistral_client import get_llm_tested, save_settings, set_llm_tested
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-old"})
        set_llm_tested(db, True)
        assert get_llm_tested(db) is True

        # Changer la cle invalide le dernier test reussi.
        save_settings(db, {"api_key": "sk-new"})
        assert get_llm_tested(db) is False
    finally:
        db.close()

    body = client.get("/api/v1/health").json()
    assert body["llm"] == "untested"
