"""Server-side password hashing (PBKDF2-HMAC-SHA256, stdlib only).

Local-account passwords used to be hashed client-side and stored in browser
localStorage (email + hash directly readable via devtools). Hashing now
happens here so the credential material never leaves the backend's SQLite
database, which is protected the same way as the rest of the app's data.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 120_000
_SALT_BYTES = 16


def hash_password(password: str) -> tuple[str, str]:
    """Returns (salt_hex, hash_hex) for a freshly generated random salt."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return hmac.compare_digest(digest.hex(), hash_hex)
