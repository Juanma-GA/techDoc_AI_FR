"""Hashing utilitaire — dédup et intégrité des uploads."""

from __future__ import annotations

import hashlib


def sha256_of_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
