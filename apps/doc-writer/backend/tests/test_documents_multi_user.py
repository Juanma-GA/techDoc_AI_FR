"""Isolation par utilisateur sur /api/v1/documents (MFA pilot, §3).

Utilise `app.dependency_overrides[require_authenticated]` (pattern FastAPI
standard) plutot qu'un flux MFA reel — teste directement le filtrage par
`request.state.user`, sans dependre du service d'identite ni d'AUTHDB.

IMPORTANT : `dependency_overrides` vit sur l'objet `app` PARTAGE entre tous
les `TestClient` construits dessus -- on ne peut donc pas avoir "un override
par persona" (le dernier ecrase les precedents pour tout le monde). A la
place, un SEUL override lit l'identite depuis un header de requete
(`X-Test-User-Email`), et chaque TestClient fixe ce header par defaut : deux
clients peuvent alors s'entrelacer sans se marcher dessus."""

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
    """Le fixture `app` (conftest.py) partage sa config globale ; on nettoie
    toujours l'override apres le test pour ne pas fuiter vers d'autres tests."""
    app.dependency_overrides[require_authenticated] = _override_from_header
    yield app
    app.dependency_overrides.clear()


def _client_as(auth_app, email: str) -> TestClient:  # type: ignore[no-untyped-def]
    return TestClient(auth_app, headers={_TEST_USER_HEADER: email})


def _upload(client: TestClient, filename: str, content: bytes):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/documents", files={"files": (filename, io.BytesIO(content), "text/plain")}
    )


def test_two_users_do_not_see_each_others_documents(auth_app) -> None:  # type: ignore[no-untyped-def]
    alice = _client_as(auth_app, "alice@atexis.com")
    r = _upload(alice, "alice.txt", b"contenu d'alice")
    assert r.status_code == 200, r.text
    alice_doc_id = r.json()["uploaded"][0]["document_id"]
    assert len(alice.get("/api/v1/documents").json()) == 1

    bob = _client_as(auth_app, "bob@atexis.com")
    assert bob.get("/api/v1/documents").json() == []

    # Bob ne peut pas acceder au document d'Alice par son id -- 404, pas 403
    # (ne pas reveler l'existence du document d'un tiers).
    r404 = bob.get(f"/api/v1/documents/{alice_doc_id}/content")
    assert r404.status_code == 404

    # Alice, elle, y accede toujours.
    r_ok = alice.get(f"/api/v1/documents/{alice_doc_id}/content")
    assert r_ok.status_code == 200


def test_delete_is_scoped_to_owner(auth_app) -> None:  # type: ignore[no-untyped-def]
    alice = _client_as(auth_app, "alice@atexis.com")
    r = _upload(alice, "alice.txt", b"contenu d'alice")
    alice_doc_id = r.json()["uploaded"][0]["document_id"]

    bob = _client_as(auth_app, "bob@atexis.com")
    r_del = bob.delete(f"/api/v1/documents/{alice_doc_id}")
    assert r_del.status_code == 404  # Bob ne peut pas supprimer le doc d'Alice.

    # Toujours la : Alice le voit encore.
    assert len(alice.get("/api/v1/documents").json()) == 1


def test_same_file_content_uploaded_by_two_users_does_not_collide(auth_app) -> None:  # type: ignore[no-untyped-def]
    """Le dedup sha256 est scope par utilisateur (0003_user_scoping) : deux
    utilisateurs uploadant EXACTEMENT le meme contenu obtiennent chacun leur
    propre document, pas une collision qui exposerait l'id de l'autre."""
    alice = _client_as(auth_app, "alice@atexis.com")
    bob = _client_as(auth_app, "bob@atexis.com")

    same_content = b"contenu identique"
    r_alice = _upload(alice, "shared.txt", same_content)
    r_bob = _upload(bob, "shared.txt", same_content)

    assert r_alice.status_code == 200, r_alice.text
    assert r_bob.status_code == 200, r_bob.text
    alice_id = r_alice.json()["uploaded"][0]["document_id"]
    bob_id = r_bob.json()["uploaded"][0]["document_id"]

    assert alice_id != bob_id
    assert r_bob.json()["uploaded"][0].get("skipped") != "duplicate"

    assert len(alice.get("/api/v1/documents").json()) == 1
    assert len(bob.get("/api/v1/documents").json()) == 1


def test_reupload_by_same_user_is_still_deduped(auth_app) -> None:  # type: ignore[no-untyped-def]
    alice = _client_as(auth_app, "alice@atexis.com")
    content = b"meme fichier deux fois"

    r1 = _upload(alice, "a.txt", content)
    r2 = _upload(alice, "a.txt", content)

    assert r1.json()["uploaded"][0]["document_id"] == r2.json()["uploaded"][0]["document_id"]
    assert r2.json()["uploaded"][0]["skipped"] == "duplicate"
    assert len(alice.get("/api/v1/documents").json()) == 1
