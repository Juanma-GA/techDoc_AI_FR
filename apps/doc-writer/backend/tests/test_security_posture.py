"""_validate_security_posture() — F-02 : tier2 / bind expose doivent fail-fast
tant qu'aucune auth pleinement configuree n'existe (palier 2/3 hors standard
POC). MFA pilot (R1) : desormais conditionnel a `auth_fully_configured`,
cf. MFA_PILOT_CHECKLIST_DOC-WRITER_2026-09-14.md §2."""

from __future__ import annotations

import pytest


def test_tier1_local_bind_starts_without_error() -> None:
    from app.config import settings
    from app.main import create_app

    assert settings.tier_mode.lower() == "tier1"
    assert settings.bind_host in {"127.0.0.1", "localhost", "::1"}
    create_app()  # ne doit pas lever


def test_tier2_fails_fast_even_with_encryption_and_cors_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings
    from app.main import create_app

    monkeypatch.setattr(settings, "tier_mode", "tier2")
    monkeypatch.setattr(settings, "bind_host", "0.0.0.0")
    # Meme avec chiffrement + CORS prod correctement configures, l'absence de
    # middleware d'auth doit a elle seule bloquer le demarrage.
    monkeypatch.setattr(settings, "encryption_key", "a" * 32)
    monkeypatch.setattr(settings, "cors_origins", ["https://doc-writer.example.com"])

    with pytest.raises(RuntimeError, match="authentification"):
        create_app()


def test_exposed_bind_without_tier2_also_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.main import create_app

    # tier1 declare mais bind pousse hors localhost -> toujours bloquant.
    monkeypatch.setattr(settings, "tier_mode", "tier1")
    monkeypatch.setattr(settings, "bind_host", "0.0.0.0")

    with pytest.raises(RuntimeError, match="authentification"):
        create_app()


def test_tier2_with_partial_auth_config_still_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """auth_enabled=True seul ne suffit pas : AUTHDB + endpoint MS365 (+ CA
    bundle si https) doivent TOUS etre configures (auth_fully_configured)."""
    from app.config import settings
    from app.main import create_app

    monkeypatch.setattr(settings, "tier_mode", "tier2")
    monkeypatch.setattr(settings, "bind_host", "0.0.0.0")
    monkeypatch.setattr(settings, "encryption_key", "a" * 32)
    monkeypatch.setattr(settings, "cors_origins", ["https://doc-writer.example.com"])
    monkeypatch.setattr(settings, "auth_enabled", True)
    # AUTHDB deliberement incomplet (pas de host) -> auth_fully_configured=False.
    assert settings.auth_fully_configured is False

    with pytest.raises(RuntimeError, match="authentification"):
        create_app()


def test_tier2_starts_when_auth_fully_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """MFA pilot (R1) : bind non-local desormais autorise a demarrer une fois
    TOUT le bloc auth configure — create_app() ne declenche PAS le lifespan
    (pas de connexion Postgres reelle ici), seule la validation au boot est
    couverte."""
    from app.config import settings
    from app.main import create_app

    monkeypatch.setattr(settings, "tier_mode", "tier2")
    monkeypatch.setattr(settings, "bind_host", "0.0.0.0")
    monkeypatch.setattr(settings, "encryption_key", "a" * 32)
    monkeypatch.setattr(settings, "cors_origins", ["https://doc-writer.example.com"])
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "authdb_host", "db.internal")
    monkeypatch.setattr(settings, "authdb_database", "docwriter_auth")
    monkeypatch.setattr(settings, "authdb_user", "docwriter")
    monkeypatch.setattr(settings, "ms365_mcp_endpoint", "http://172.21.28.81/mcp/ms365/mcp")
    assert settings.auth_fully_configured is True

    create_app()  # ne doit pas lever


def test_local_bind_but_exposed_behind_proxy_fails_fast_without_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deploiement derriere reverse-proxy : uvicorn reste sur 127.0.0.1 mais
    l'app est joignable de l'exterieur. Sans `exposed_behind_proxy`, F-02
    croirait a tort etre en local et laisserait passer SANS auth. Avec le
    flag, la validation stricte s'applique et bloque si l'auth n'est pas
    pleinement configuree."""
    from app.config import settings
    from app.main import create_app

    monkeypatch.setattr(settings, "tier_mode", "tier1")
    monkeypatch.setattr(settings, "bind_host", "127.0.0.1")
    monkeypatch.setattr(settings, "exposed_behind_proxy", True)
    # Rien d'auth configure -> doit bloquer malgre le bind local.
    monkeypatch.setattr(settings, "auth_enabled", False)

    with pytest.raises(RuntimeError, match="authentification"):
        create_app()


def test_local_bind_without_proxy_flag_still_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garde-fou de non-regression : sans le flag, un bind local en tier1
    demarre exactement comme avant (comportement tier1 inchange)."""
    from app.config import settings
    from app.main import create_app

    monkeypatch.setattr(settings, "tier_mode", "tier1")
    monkeypatch.setattr(settings, "bind_host", "127.0.0.1")
    monkeypatch.setattr(settings, "exposed_behind_proxy", False)

    create_app()  # ne doit pas lever
