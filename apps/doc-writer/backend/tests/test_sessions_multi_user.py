"""Isolation par utilisateur sur /api/v1/sessions (MFA pilot, §3).

Meme pattern que test_documents_multi_user.py : override
`require_authenticated` via un header de requete (X-Test-User-Email), pas de
flux MFA reel."""

from __future__ import annotations

import io

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


def test_two_users_do_not_see_each_others_sessions(auth_app) -> None:  # type: ignore[no-untyped-def]
    alice = _client_as(auth_app, "alice@atexis.com")
    r = alice.post("/api/v1/sessions", json={"title": "Alice", "scope_doc_ids": [], "lang": "fr"})
    assert r.status_code == 200, r.text
    alice_session_id = r.json()["id"]

    bob = _client_as(auth_app, "bob@atexis.com")
    assert bob.get("/api/v1/sessions").json() == []

    r404 = bob.get(f"/api/v1/sessions/{alice_session_id}/messages")
    assert r404.status_code == 404

    r_del = bob.delete(f"/api/v1/sessions/{alice_session_id}")
    assert r_del.status_code == 404

    # Toujours la pour Alice.
    assert len(alice.get("/api/v1/sessions").json()) == 1


def test_session_cannot_reference_another_users_document(auth_app) -> None:  # type: ignore[no-untyped-def]
    """Sans ce garde-fou, Bob pourrait mettre l'id d'un document d'Alice dans
    scope_doc_ids et en faire fuiter le contenu dans sa propre generation."""
    alice = _client_as(auth_app, "alice@atexis.com")
    r_doc = alice.post(
        "/api/v1/documents",
        files={"files": ("alice-private.txt", io.BytesIO(b"secret d'alice"), "text/plain")},
    )
    alice_doc_id = r_doc.json()["uploaded"][0]["document_id"]

    bob = _client_as(auth_app, "bob@atexis.com")
    r_session = bob.post(
        "/api/v1/sessions",
        json={"title": "Bob essaie de lire Alice", "scope_doc_ids": [alice_doc_id], "lang": "fr"},
    )
    assert r_session.status_code == 400, r_session.text
    assert r_session.json()["code"] == "DOCUMENT_NOT_OWNED"


def test_session_cannot_use_another_users_document_as_template(auth_app) -> None:  # type: ignore[no-untyped-def]
    alice = _client_as(auth_app, "alice@atexis.com")
    r_doc = alice.post(
        "/api/v1/documents",
        files={"files": ("alice-template.txt", io.BytesIO(b"template d'alice"), "text/plain")},
    )
    alice_doc_id = r_doc.json()["uploaded"][0]["document_id"]

    bob = _client_as(auth_app, "bob@atexis.com")
    r_session = bob.post(
        "/api/v1/sessions",
        json={
            "title": "Bob essaie le template d'Alice",
            "scope_doc_ids": [],
            "template_doc_id": alice_doc_id,
            "lang": "fr",
        },
    )
    assert r_session.status_code == 400, r_session.text
    assert r_session.json()["code"] == "DOCUMENT_NOT_OWNED"


def test_session_with_own_document_as_scope_succeeds(auth_app) -> None:  # type: ignore[no-untyped-def]
    alice = _client_as(auth_app, "alice@atexis.com")
    r_doc = alice.post(
        "/api/v1/documents",
        files={"files": ("alice.txt", io.BytesIO(b"contenu d'alice"), "text/plain")},
    )
    alice_doc_id = r_doc.json()["uploaded"][0]["document_id"]

    r_session = alice.post(
        "/api/v1/sessions",
        json={"title": "Alice", "scope_doc_ids": [alice_doc_id], "lang": "fr"},
    )
    assert r_session.status_code == 200, r_session.text
