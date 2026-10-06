"""Encryption utilities for sensitive data storage.

Uses Fernet (symmetric encryption) from cryptography library.
Secrets are encrypted before storage in DB and decrypted on retrieval.
"""

from __future__ import annotations

import structlog
from cryptography.fernet import Fernet, InvalidToken

logger = structlog.get_logger(__name__)


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""


class SecretManager:
    """Manages encryption and decryption of sensitive data.

    Uses Fernet (symmetric encryption with AES 128 in CBC mode). Key must be
    32 url-safe base64-encoded bytes. Key absent -> encryption disabled
    (plaintext passthrough, dev/local only).
    """

    def __init__(self, encryption_key: str | None) -> None:
        self._enabled = bool(encryption_key)
        self._cipher: Fernet | None = None
        if self._enabled and encryption_key:
            try:
                self._cipher = Fernet(encryption_key.encode())
            except Exception as e:
                raise EncryptionError(f"Invalid encryption key: {e}") from e

    @property
    def enabled(self) -> bool:
        return self._enabled

    def encrypt(self, plaintext: str) -> str:
        if not self._enabled or not self._cipher:
            logger.warning("encryption_disabled_plaintext_secret")
            return plaintext
        try:
            return self._cipher.encrypt(plaintext.encode()).decode()
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, ciphertext: str) -> str:
        if not self._enabled or not self._cipher:
            return ciphertext
        try:
            return self._cipher.decrypt(ciphertext.encode()).decode()
        except InvalidToken as e:
            raise EncryptionError("Decryption failed - invalid token or wrong key") from e
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}") from e


def generate_key() -> str:
    """Generate a new Fernet encryption key (base64-encoded 32-byte, len 44)."""
    return Fernet.generate_key().decode()
