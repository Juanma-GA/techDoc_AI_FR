"""_validate_security_posture() — F-02 : tier2 / bind expose doivent fail-fast
tant qu'aucun middleware d'auth n'existe (palier 2/3 hors standard POC)."""

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
