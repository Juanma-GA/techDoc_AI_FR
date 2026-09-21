"""Encryption utilities for sensitive data storage.

Uses AES-256-GCM (via `cryptography`'s AEAD primitive) — the approved
algorithm (CLAUDE.md policy doc 144 §6: AES-256, RSA-2048, ECC). Secrets are
encrypted before storage in DB and decrypted on retrieval.

F-04 (hardening 2026-09-14): this replaced Fernet, whose underlying cipher is
AES-**128**-CBC + HMAC — below the mandated AES-256. Ciphertext format changed
(nonce + tag are no longer a Fernet token), so a key generated for the old
scheme cannot decrypt values encrypted before this change; see README/hardening
notes if migrating an existing deployment with stored secrets.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

_KEY_BYTES = 32  # AES-256.
_NONCE_BYTES = 12  # Recommended GCM nonce size (96 bits).


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""


class SecretManager:
    """Manages encryption and decryption of sensitive data.

    Uses AES-256-GCM (authenticated encryption). Key must decode to exactly
    32 raw bytes (base64, url-safe, as produced by `generate_key()`). Key
    absent -> encryption disabled (plaintext passthrough, dev/local only).
    Stored value = base64(nonce[12] + ciphertext_with_tag).
    """

    def __init__(self, encryption_key: str | None) -> None:
        self._enabled = bool(encryption_key)
        self._aesgcm: AESGCM | None = None
        if self._enabled and encryption_key:
            try:
                key_bytes = base64.urlsafe_b64decode(encryption_key.encode())
                if len(key_bytes) != _KEY_BYTES:
                    raise ValueError(f"key must decode to {_KEY_BYTES} bytes (AES-256)")
                self._aesgcm = AESGCM(key_bytes)
            except Exception as e:
                raise EncryptionError(f"Invalid encryption key: {e}") from e

    @property
    def enabled(self) -> bool:
        return self._enabled

    def encrypt(self, plaintext: str) -> str:
        if not self._enabled or not self._aesgcm:
            logger.warning("Encryption disabled - storing plaintext (INSECURE)")
            return plaintext
        try:
            nonce = os.urandom(_NONCE_BYTES)
            ct = self._aesgcm.encrypt(nonce, plaintext.encode(), None)
            return base64.urlsafe_b64encode(nonce + ct).decode()
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, ciphertext: str) -> str:
        if not self._enabled or not self._aesgcm:
            return ciphertext
        try:
            raw = base64.urlsafe_b64decode(ciphertext.encode())
            nonce, ct = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
            return self._aesgcm.decrypt(nonce, ct, None).decode()
        except InvalidTag as e:
            raise EncryptionError("Decryption failed - invalid token or wrong key") from e
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}") from e


def generate_key() -> str:
    """Generate a new AES-256 key (32 random bytes, url-safe base64, len 44)."""
    return base64.urlsafe_b64encode(os.urandom(_KEY_BYTES)).decode()


def load_or_create_local_key(path: Path) -> str:
    """Auto-provision an at-rest encryption key on local disk (F-05).

    Used only when no `ENCRYPTION_KEY` is configured via env/`.env` (the
    `tier1` local default) so secrets in `AppConfig` are never stored in
    cleartext just because the operator didn't set one explicitly. The key
    lives next to the SQLite DB/storage dir — already gitignored — and is
    generated once, then reused on every subsequent call.
    """
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
        if key:
            return key
    key = generate_key()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass  # Best-effort (e.g. no-op on Windows filesystems).
    return key
