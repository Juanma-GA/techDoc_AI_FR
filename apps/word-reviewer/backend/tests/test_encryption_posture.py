"""Chiffrement de la cle Mistral au repos + garde-fou de posture de securite.

Miroir du durcissement corpus-agent : cle Mistral chiffree en DB (Fernet) et
refus de demarrer en bind expose sans chiffrement ni CORS prod.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.core.encryption import SecretManager, generate_key
from app.core.mistral_client import _read_config, get_effective_settings, save_settings
from app.db.models import AppConfig
from app.db.session import SessionLocal


def test_encryption_roundtrip() -> None:
    key = generate_key()
    mgr = SecretManager(key)
    assert mgr.enabled
    token = mgr.encrypt("sk-secret-123")
    assert token != "sk-secret-123"
    assert mgr.decrypt(token) == "sk-secret-123"


def test_disabled_encryption_passthrough() -> None:
    mgr = SecretManager(None)
    assert not mgr.enabled
    assert mgr.encrypt("x") == "x"
    assert mgr.decrypt("x") == "x"


def test_mistral_key_stored_encrypted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avec ENCRYPTION_KEY, la valeur brute en DB est chiffree ; get_effective
    la dechiffre."""
    monkeypatch.setattr(settings, "encryption_key", generate_key())
    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-plit-abcdef1234567890"})
        raw = db.get(AppConfig, "MISTRAL_API_KEY")
        assert raw is not None
        assert raw.value != "sk-plit-abcdef1234567890"  # chiffre au repos
        assert _read_config(db, "MISTRAL_API_KEY") == "sk-plit-abcdef1234567890"
        assert get_effective_settings(db)["api_key"] == "sk-plit-abcdef1234567890"
    finally:
        # Nettoyage : retire la cle pour ne pas polluer les autres tests.
        row = db.get(AppConfig, "MISTRAL_API_KEY")
        if row is not None:
            db.delete(row)
            db.commit()
        db.close()


def test_posture_ok_when_local_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import _validate_security_posture

    monkeypatch.setattr(settings, "bind_host", "127.0.0.1")
    _validate_security_posture()  # ne leve pas


def test_posture_fails_exposed_without_encryption(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import _validate_security_posture

    monkeypatch.setattr(settings, "bind_host", "0.0.0.0")
    monkeypatch.setattr(settings, "encryption_key", "")
    monkeypatch.setattr(settings, "cors_origins", ["https://wr.example.com"])
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        _validate_security_posture()


def test_posture_fails_exposed_with_local_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import _validate_security_posture

    monkeypatch.setattr(settings, "bind_host", "0.0.0.0")
    monkeypatch.setattr(settings, "encryption_key", generate_key())
    monkeypatch.setattr(settings, "cors_origins", ["http://localhost:5173"])
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _validate_security_posture()


def test_posture_ok_exposed_when_hardened(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import _validate_security_posture

    monkeypatch.setattr(settings, "bind_host", "0.0.0.0")
    monkeypatch.setattr(settings, "encryption_key", generate_key())
    monkeypatch.setattr(settings, "cors_origins", ["https://wr.example.com"])
    _validate_security_posture()  # ne leve pas
