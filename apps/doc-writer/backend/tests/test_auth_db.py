"""app.core.auth_db — AUTHDB (MFA pilot, R1).

Pas de Postgres reel disponible dans cet environnement (cf. §0 du checklist,
MFA_PILOT_CHECKLIST_DOC-WRITER_2026-09-14.md) : ces tests couvrent la logique
qui ne necessite PAS de connexion (normalisation d'email, validation de role,
posture fail-closed avant initialize()). Les tests d'integration reels contre
un Postgres restent a faire une fois l'instance provisionnee (§0)."""

from __future__ import annotations

import pytest


def test_normalize_email_trims_and_lowercases() -> None:
    from app.core.auth_db import normalize_email

    assert normalize_email("  Jane.DOE@Atexis.com  ") == "jane.doe@atexis.com"
    assert normalize_email("") == ""
    assert normalize_email(None) == ""  # type: ignore[arg-type]


def test_create_user_rejects_invalid_role_before_touching_the_db() -> None:
    """La validation de role se fait AVANT tout appel a la DB (create_user
    verifie `role in VALID_ROLES` avant get_user_by_email) — verifiable sans
    connexion Postgres."""
    from app.core.auth_db import AuthDBService

    # Instance non-initialisee : n'importe quel appel qui atteindrait _execute
    # leverait RuntimeError("AuthDB non initialisee"). Un role invalide doit
    # lever ValueError AVANT cela.
    service = AuthDBService()
    with pytest.raises(ValueError, match="Role inconnu"):
        service.create_user("jane.doe@atexis.com", "superuser", "admin@atexis.com")


def test_update_role_rejects_invalid_role_before_touching_the_db() -> None:
    from app.core.auth_db import AuthDBService

    service = AuthDBService()
    with pytest.raises(ValueError, match="Role inconnu"):
        service.update_role("jane.doe@atexis.com", "superuser")


def test_uninitialized_service_fails_closed_on_read() -> None:
    """Sans initialize() (donc sans connexion Postgres), toute lecture doit
    lever plutot que renvoyer un resultat par defaut — fail-closed, jamais
    de repli silencieux (pas d'equivalent ChromaDB pour l'autorisation)."""
    from app.core.auth_db import AuthDBService

    service = AuthDBService()
    assert service.is_initialized is False
    assert service.get_status() == "not_initialized"
    with pytest.raises(RuntimeError, match="AuthDB non initialisee"):
        service.get_user_by_email("jane.doe@atexis.com")


def test_get_auth_db_service_returns_the_same_singleton() -> None:
    from app.core.auth_db import AuthDBService, get_auth_db_service

    assert get_auth_db_service() is get_auth_db_service()
    assert get_auth_db_service() is AuthDBService()


# ---------------------------------------------------------------------------
# §0 bootstrap : premier admin seme si la table est vide. Teste avec une
# connexion factice (duck-typing du sous-ensemble de l'API psycopg utilise) —
# pas besoin d'un Postgres reel pour verifier la DECISION (compter, inserer
# ou pas), seulement pour l'executer en vrai (hors de portee sans §0).
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, row: dict | None) -> None:
        self._row = row

    def fetchone(self) -> dict | None:
        return self._row


class _FakeConn:
    def __init__(self, row_count: int) -> None:
        self.row_count = row_count
        self.executed: list[tuple[str, object]] = []

    def execute(self, sql: str, params: object = None) -> _FakeCursor:
        self.executed.append((sql, params))
        if "SELECT COUNT" in sql:
            return _FakeCursor({"n": self.row_count})
        return _FakeCursor(None)


def test_seed_admin_skipped_when_no_seed_email_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.core.auth_db import AuthDBService

    monkeypatch.setattr(settings, "auth_seed_admin_email", "")
    conn = _FakeConn(row_count=0)
    AuthDBService()._seed_admin_if_empty(conn)  # type: ignore[arg-type]

    assert not any("INSERT" in sql for sql, _ in conn.executed)


def test_seed_admin_skipped_when_table_not_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.core.auth_db import AuthDBService

    monkeypatch.setattr(settings, "auth_seed_admin_email", "ana.catalan@atexis.com")
    conn = _FakeConn(row_count=3)
    AuthDBService()._seed_admin_if_empty(conn)  # type: ignore[arg-type]

    assert not any("INSERT" in sql for sql, _ in conn.executed)


def test_seed_admin_inserted_when_configured_and_table_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.core.auth_db import AuthDBService

    monkeypatch.setattr(settings, "auth_seed_admin_email", "  Ana.Catalan@Atexis.com  ")
    conn = _FakeConn(row_count=0)
    AuthDBService()._seed_admin_if_empty(conn)  # type: ignore[arg-type]

    inserts = [(sql, params) for sql, params in conn.executed if "INSERT" in sql]
    assert len(inserts) == 1
    _sql, params = inserts[0]
    assert params == ("ana.catalan@atexis.com",)  # normalise (trim + minuscules)
