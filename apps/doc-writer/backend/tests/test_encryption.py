"""SecretManager — F-04 : chiffrement au repos AES-256-GCM (mandat doc 144 §6),
remplace Fernet (AES-128-CBC), en dessous du mandat. Inclut F-05 : cle locale
auto-provisionnee quand ENCRYPTION_KEY est vide (plus de repli en clair par
defaut en tier1)."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.encryption import EncryptionError, SecretManager, generate_key, load_or_create_local_key


def test_generate_key_decodes_to_32_bytes_aes_256() -> None:
    key = generate_key()
    raw = base64.urlsafe_b64decode(key.encode())
    assert len(raw) == 32


def test_encrypt_uses_aes_256_gcm_under_the_hood() -> None:
    """Le format stocke doit etre dechiffrable directement via AESGCM (pas Fernet)."""
    key = generate_key()
    manager = SecretManager(key)
    ciphertext = manager.encrypt("sk-super-secret")

    raw = base64.urlsafe_b64decode(ciphertext.encode())
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(base64.urlsafe_b64decode(key.encode()))
    assert aesgcm.decrypt(nonce, ct, None) == b"sk-super-secret"


def test_encrypt_then_decrypt_roundtrip() -> None:
    key = generate_key()
    manager = SecretManager(key)
    ciphertext = manager.encrypt("my-mistral-key")
    assert ciphertext != "my-mistral-key"
    assert manager.decrypt(ciphertext) == "my-mistral-key"


def test_decrypt_with_wrong_key_raises() -> None:
    manager_a = SecretManager(generate_key())
    manager_b = SecretManager(generate_key())
    ciphertext = manager_a.encrypt("secret")
    with pytest.raises(EncryptionError):
        manager_b.decrypt(ciphertext)


def test_disabled_when_no_key_is_plaintext_passthrough() -> None:
    manager = SecretManager(None)
    assert manager.enabled is False
    assert manager.encrypt("plain") == "plain"
    assert manager.decrypt("plain") == "plain"


def test_invalid_key_raises_at_construction() -> None:
    with pytest.raises(EncryptionError):
        SecretManager("not-a-valid-base64-key!!")


def test_load_or_create_local_key_generates_once_then_reuses(tmp_path: Path) -> None:
    key_path = tmp_path / "sub" / ".encryption_key"
    assert not key_path.exists()

    first = load_or_create_local_key(key_path)
    assert key_path.exists()
    raw = base64.urlsafe_b64decode(first.encode())
    assert len(raw) == 32

    second = load_or_create_local_key(key_path)
    assert second == first  # Meme fichier relu, pas regenere.


def test_get_secret_manager_auto_provisions_key_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F-05 : sans ENCRYPTION_KEY, save_settings/_read_config chiffrent quand
    meme (repli en clair supprime) grace a la cle auto-provisionnee."""
    from app.config import settings
    from app.core.mistral_client import save_settings
    from app.db.session import SessionLocal
    from app.db import models

    key_path = tmp_path / ".encryption_key"
    monkeypatch.setattr(settings, "encryption_key", "")
    monkeypatch.setattr(settings, "encryption_key_path", str(key_path))

    db = SessionLocal()
    try:
        save_settings(db, {"api_key": "sk-plaintext-should-not-appear"})
        row = db.get(models.AppConfig, "MISTRAL_API_KEY")
        assert row is not None
        # La valeur stockee ne doit JAMAIS etre le secret en clair.
        assert row.value != "sk-plaintext-should-not-appear"
        assert key_path.exists()

        from app.core.mistral_client import get_effective_settings

        assert get_effective_settings(db)["api_key"] == "sk-plaintext-should-not-appear"
    finally:
        db.query(models.AppConfig).delete()
        db.commit()
        db.close()
