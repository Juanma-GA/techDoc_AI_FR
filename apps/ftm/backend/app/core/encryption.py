"""Encryption utilities for sensitive data storage.

Uses Fernet (symmetric encryption) from cryptography library.
Secrets are encrypted before storage in DB and decrypted on retrieval.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""
    pass


class SecretManager:
    """Manages encryption and decryption of sensitive data.
    
    Uses Fernet (symmetric encryption with AES 128 in CBC mode).
    Key must be 32 url-safe base64-encoded bytes.
    
    Example:
        manager = SecretManager(encryption_key)
        encrypted = manager.encrypt("my-secret-api-key")
        decrypted = manager.decrypt(encrypted)
    """
    
    def __init__(self, encryption_key: str | None):
        """Initialize with encryption key.
        
        Args:
            encryption_key: Base64-encoded Fernet key or None for disabled encryption
        
        Raises:
            EncryptionError: If key is invalid
        """
        self._enabled = bool(encryption_key)
        self._cipher: Fernet | None = None
        
        if self._enabled:
            try:
                self._cipher = Fernet(encryption_key.encode())
            except Exception as e:
                raise EncryptionError(f"Invalid encryption key: {e}") from e
    
    @property
    def enabled(self) -> bool:
        """Check if encryption is enabled."""
        return self._enabled
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string.
        
        Args:
            plaintext: String to encrypt
        
        Returns:
            Base64-encoded encrypted string
        
        Raises:
            EncryptionError: If encryption fails
        """
        if not self._enabled or not self._cipher:
            # Encryption disabled - return plaintext (dev mode only)
            logger.warning("Encryption disabled - storing plaintext (INSECURE)")
            return plaintext
        
        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt encrypted string.
        
        Args:
            ciphertext: Base64-encoded encrypted string
        
        Returns:
            Decrypted plaintext string
        
        Raises:
            EncryptionError: If decryption fails
        """
        if not self._enabled or not self._cipher:
            # Encryption disabled - return as-is (dev mode only)
            return ciphertext
        
        try:
            decrypted_bytes = self._cipher.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except InvalidToken as e:
            raise EncryptionError("Decryption failed - invalid token or wrong key") from e
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}") from e
    
    def rotate_key(self, old_key: str, new_key: str, ciphertext: str) -> str:
        """Re-encrypt data with new key.
        
        Args:
            old_key: Previous encryption key
            new_key: New encryption key
            ciphertext: Data encrypted with old key
        
        Returns:
            Data encrypted with new key
        
        Raises:
            EncryptionError: If rotation fails
        """
        old_manager = SecretManager(old_key)
        plaintext = old_manager.decrypt(ciphertext)
        
        new_manager = SecretManager(new_key)
        return new_manager.encrypt(plaintext)


def generate_key() -> str:
    """Generate a new Fernet encryption key.
    
    Returns:
        Base64-encoded 32-byte key suitable for Fernet
    
    Example:
        >>> key = generate_key()
        >>> print(key)
        'vF8dXxK3qJ...'  # 44 characters
    """
    return Fernet.generate_key().decode()
