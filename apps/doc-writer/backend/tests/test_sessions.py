"""Routes /api/v1/sessions — CRUD + messages."""

from __future__ import annotations


def test_create_list_delete_session(client) -> None:
    r = client.post(
        "/api/v1/sessions",
        json={"title": "Synthèse Q3", "scope_doc_ids": [], "lang": "fr"},
    )
    assert r.status_code == 200, r.text
    session = r.json()
    assert session["title"] == "Synthèse Q3"
    assert session["lang"] == "fr"
    assert session["scope_doc_ids"] == []
    session_id = session["id"]

    r2 = client.get("/api/v1/sessions")
    assert r2.status_code == 200
    assert len(r2.json()) == 1

    r3 = client.get(f"/api/v1/sessions/{session_id}/messages")
    assert r3.status_code == 200
    assert r3.json() == []

    r4 = client.delete(f"/api/v1/sessions/{session_id}")
    assert r4.status_code == 204
    assert client.get("/api/v1/sessions").json() == []


def test_messages_unknown_session_returns_404(client) -> None:
    r = client.get(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000/messages"
    )
    assert r.status_code == 404
    assert r.json()["code"] == "SESSION_NOT_FOUND"


def test_ask_without_mistral_returns_400(client) -> None:
    r = client.post(
        "/api/v1/sessions",
        json={"title": "x", "scope_doc_ids": [], "lang": "fr"},
    )
    session_id = r.json()["id"]
    r2 = client.post(
        f"/api/v1/sessions/{session_id}/ask",
        json={"question": "Bonjour"},
    )
    assert r2.status_code == 400
    assert r2.json()["code"] == "MISTRAL_NOT_CONFIGURED"
