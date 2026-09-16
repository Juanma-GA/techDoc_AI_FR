"""Shared `atexispocs_session` cookie — sign/verify (MFA portal SSO, option A).

The portal issues this cookie after a successful MFA; every app verifies it
with the same two shared secrets. Kept deliberately free of any AUTHDB / role
logic: the portal only proves "this email passed corporate MFA". Authorization
(who may use a given app, with what role) is each app's own concern.

Payload is base64(JSON) + "." + HMAC-SHA256(payload). The MS365
`verification_token` embedded in the payload is AESGCM-encrypted at rest (it is
a bearer credential for the identity service) — same posture as doc-writer.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import settings
from app.core.encryption import SecretManager, load_or_create_local_key


@dataclass
class VerifiedIdentity:
    """Identity carried by a valid session cookie. `verification_token` is the
    plaintext MS365 bearer token for this request only — never logged."""

    email: str
    display_name: str
    verification_token: str


def _hmac_secret() -> str:
    return load_or_create_local_key(Path(settings.session_hmac_secret_path))


def _enc_key() -> str:
    return load_or_create_local_key(Path(settings.session_enc_key_path))


def _sign(payload_b64: str) -> str:
    digest = hmac.new(_hmac_secret().encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_session_token(email: str, display_name: str, verification_token: str) -> str:
    payload = {
        "email": email,
        "display_name": display_name,
        "vt": SecretManager(_enc_key()).encrypt(verification_token),
        "exp": int(time.time()) + settings.session_ttl_minutes * 60,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_session_token(token: str) -> Optional[VerifiedIdentity]:
    """Verify + decode, or None if invalid/expired/tampered. Does NOT call the
    identity service (that's the caller's per-request revalidation step)."""
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(payload_b64), signature):
        return None
    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:  # noqa: BLE001
        return None
    if payload.get("exp", 0) < time.time():
        return None
    try:
        vt = SecretManager(_enc_key()).decrypt(payload["vt"])
        if not vt:
            return None
        return VerifiedIdentity(
            email=payload["email"],
            display_name=payload.get("display_name", ""),
            verification_token=vt,
        )
    except (KeyError, TypeError):
        return None
