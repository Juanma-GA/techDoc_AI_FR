"""Isolation par utilisateur sur /api/v1/sessions/{id}/export & co (§3, MFA pilot).

Meme pattern que test_sessions_multi_user.py."""

from __future__ import annotations

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.core.auth import AuthenticatedUser, require_authenticated

_TEST_USER_HEADER = "X-Test-User-Email"


def _override_from_header(request: Request) -> AuthenticatedUser | None:
    email = request.headers.get(_TEST_USER_HEADER)
    if not email:
        return None
    return AuthenticatedUser(email=email, display_name=email, role="user", verification_token="test-vt")


@pytest.fixture
def auth_app(app):  # type: ignore[no-untyped-def]
    app.dependency_overrides[require_authenticated] = _override_from_header
    yield app
    app.dependency_overrides.clear()


def _client_as(auth_app, email: str) -> TestClient:  # type: ignore[no-untyped-def]
    return TestClient(auth_app, headers={_TEST_USER_HEADER: email})


def test_export_endpoints_404_for_a_foreign_session(auth_app) -> None:  # type: ignore[no-untyped-def]
    alice = _client_as(auth_app, "alice@atexis.com")
    r = alice.post("/api/v1/sessions", json={"title": "Alice", "scope_doc_ids": [], "lang": "fr"})
    session_id = r.json()["id"]

    bob = _client_as(auth_app, "bob@atexis.com")
    checks = [
        bob.get(f"/api/v1/sessions/{session_id}/export?format=md"),
        bob.post(f"/api/v1/sessions/{session_id}/preview-pptx"),
        bob.post(f"/api/v1/sessions/{session_id}/refill-zones", json={"zone_ids": []}),
    ]
    for r_bob in checks:
        assert r_bob.status_code == 404, f"{r_bob.request.method} {r_bob.request.url} -> {r_bob.status_code}: {r_bob.text}"
        assert r_bob.json()["code"] == "SESSION_NOT_FOUND"
