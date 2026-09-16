"""app.core.auth — verification de la cookie PARTAGEE emise par le portal
(SSO option A), expiration, falsification. Pas de Postgres/service d'identite
reel requis : logique pure du jeton + dependances FastAPI.

doc-writer n'EMET plus de cookie (le portal le fait), donc les tests
construisent un jeton au format partage via `_make_token`, en reutilisant les
internes de doc-writer (`_sign`/`_enc_key`) -> garanti compatible avec
`verify_session_token`."""

from __future__ import annotations

import base64
import json
import time

import pytest


def _configure_auth(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from app.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "session_hmac_secret_path", str(tmp_path / ".hmac"))
    monkeypatch.setattr(settings, "session_enc_key_path", str(tmp_path / ".enc"))


def _make_token(email: str, display_name: str, vt: str, ttl_seconds: int = 3600) -> str:
    """Construit une cookie au format partage (identique au portal)."""
    from app.core import auth as A
    from app.core.encryption import SecretManager

    payload = {
        "email": email,
        "display_name": display_name,
        "vt": SecretManager(A._enc_key()).encrypt(vt),
        "exp": int(time.time()) + ttl_seconds,
    }
    pb = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{pb}.{A._sign(pb)}"


def test_verify_shared_cookie_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from app.core.auth import verify_session_token

    _configure_auth(monkeypatch, tmp_path)
    token = _make_token("jane.doe@atexis.com", "Jane Doe", "vt-secret-upstream")
    user = verify_session_token(token)
    assert user is not None
    assert user.email == "jane.doe@atexis.com"
    assert user.display_name == "Jane Doe"
    # Le role n'est PAS dans la cookie (renseigne via l'AUTHDB) -> "" ici.
    assert user.role == ""
    # Le verification_token en clair n'apparait jamais dans le jeton serialise.
    assert "vt-secret-upstream" not in token
    assert user.verification_token == "vt-secret-upstream"


def test_verify_session_token_rejects_tampered_signature(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from app.core.auth import verify_session_token

    _configure_auth(monkeypatch, tmp_path)
    token = _make_token("jane.doe@atexis.com", "Jane Doe", "vt-secret")
    payload_b64, _sig = token.split(".", 1)
    tampered = f"{payload_b64}.not-the-real-signature"

    assert verify_session_token(tampered) is None


def test_verify_session_token_rejects_expired(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from app.core.auth import verify_session_token

    _configure_auth(monkeypatch, tmp_path)
    token = _make_token("jane.doe@atexis.com", "Jane Doe", "vt-secret", ttl_seconds=-1)

    assert verify_session_token(token) is None


def test_verify_session_token_rejects_garbage() -> None:
    from app.core.auth import verify_session_token

    assert verify_session_token("not-even-a-valid-token") is None
    assert verify_session_token("") is None


def test_require_authenticated_is_noop_when_auth_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.requests import Request

    from app.config import settings
    from app.core.auth import require_authenticated

    monkeypatch.setattr(settings, "auth_enabled", False)
    scope = {"type": "http", "headers": [], "state": {}}
    request = Request(scope)

    assert require_authenticated(request) is None


def test_require_authenticated_raises_401_when_enabled_and_no_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException
    from starlette.requests import Request

    from app.config import settings
    from app.core.auth import require_authenticated

    monkeypatch.setattr(settings, "auth_enabled", True)
    scope = {"type": "http", "headers": [], "state": {}}
    request = Request(scope)
    request.state.user = None

    with pytest.raises(HTTPException) as exc_info:
        require_authenticated(request)
    assert exc_info.value.status_code == 401


def test_require_admin_raises_403_for_non_admin_role(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException
    from starlette.requests import Request

    from app.config import settings
    from app.core.auth import AuthenticatedUser, require_admin

    monkeypatch.setattr(settings, "auth_enabled", True)
    scope = {"type": "http", "headers": [], "state": {}}
    request = Request(scope)
    request.state.user = AuthenticatedUser(
        email="jane.doe@atexis.com", display_name="Jane Doe", role="user", verification_token="vt"
    )

    with pytest.raises(HTTPException) as exc_info:
        require_admin(request)
    assert exc_info.value.status_code == 403


def test_require_admin_allows_admin_role(monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.requests import Request

    from app.config import settings
    from app.core.auth import AuthenticatedUser, require_admin

    monkeypatch.setattr(settings, "auth_enabled", True)
    scope = {"type": "http", "headers": [], "state": {}}
    request = Request(scope)
    request.state.user = AuthenticatedUser(
        email="admin@atexis.com", display_name="Admin", role="admin", verification_token="vt"
    )

    user = require_admin(request)
    assert user is not None
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_resolve_authenticated_user_rejects_when_identity_service_denies(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Meme avec un jeton de session valide, resolve_authenticated_user doit
    rejeter (None) si ms365_identity_validate renvoie valid=False ou
    mfa_verified=False — jamais faire confiance au seul cache local."""
    from app.core import ms365_identity_client
    from app.core.auth import resolve_authenticated_user

    _configure_auth(monkeypatch, tmp_path)
    token = _make_token("jane.doe@atexis.com", "Jane Doe", "vt-secret")

    async def _fake_validate(verification_token: str) -> dict:  # type: ignore[no-untyped-def]
        return {"valid": False, "user": {"email": "jane.doe@atexis.com", "mfa_verified": False}}

    monkeypatch.setattr(ms365_identity_client, "validate", _fake_validate)

    assert await resolve_authenticated_user(token) is None


@pytest.mark.asyncio
async def test_resolve_authenticated_user_rejects_when_identity_service_unreachable(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Fail-closed : une erreur du service d'identite (timeout, 5xx, etc.)
    doit rejeter la session, jamais l'accepter par defaut."""
    from app.core import ms365_identity_client
    from app.core.auth import resolve_authenticated_user

    _configure_auth(monkeypatch, tmp_path)
    token = _make_token("jane.doe@atexis.com", "Jane Doe", "vt-secret")

    async def _boom(verification_token: str) -> dict:  # type: ignore[no-untyped-def]
        raise ms365_identity_client.Ms365IdentityError("upstream down")

    monkeypatch.setattr(ms365_identity_client, "validate", _boom)

    assert await resolve_authenticated_user(token) is None
