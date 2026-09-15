"""admin/reset/* gates on the `admin` role once auth is active (§3, MFA pilot).

Meme pattern d'override que les autres tests multi-utilisateur."""

from __future__ import annotations

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.core.auth import AuthenticatedUser, require_admin, require_authenticated

_TEST_USER_HEADER = "X-Test-User-Email"
_TEST_ROLE_HEADER = "X-Test-User-Role"


def _override_authenticated(request: Request) -> AuthenticatedUser | None:
    email = request.headers.get(_TEST_USER_HEADER)
    if not email:
        return None
    role = request.headers.get(_TEST_ROLE_HEADER, "user")
    return AuthenticatedUser(email=email, display_name=email, role=role, verification_token="test-vt")


def _override_admin(request: Request) -> AuthenticatedUser | None:
    from fastapi import HTTPException, status

    user = _override_authenticated(request)
    if user is None:
        return None
    if not user.has_role("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


@pytest.fixture
def auth_app(app):  # type: ignore[no-untyped-def]
    app.dependency_overrides[require_authenticated] = _override_authenticated
    app.dependency_overrides[require_admin] = _override_admin
    yield app
    app.dependency_overrides.clear()


def _client_as(auth_app, email: str, role: str = "user") -> TestClient:  # type: ignore[no-untyped-def]
    return TestClient(auth_app, headers={_TEST_USER_HEADER: email, _TEST_ROLE_HEADER: role})


def test_reset_forbidden_for_non_admin_user(auth_app) -> None:  # type: ignore[no-untyped-def]
    user_client = _client_as(auth_app, "user@atexis.com", role="user")
    r = user_client.post("/api/v1/admin/reset/all", json={"confirm": "all"})
    assert r.status_code == 403


def test_reset_allowed_for_admin_user(auth_app) -> None:  # type: ignore[no-untyped-def]
    admin_client = _client_as(auth_app, "admin@atexis.com", role="admin")
    r = admin_client.post("/api/v1/admin/reset/all", json={"confirm": "all"})
    assert r.status_code == 200, r.text
