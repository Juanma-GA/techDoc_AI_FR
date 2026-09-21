"""Routes /api/v1/admin — F-06 : confirmation serveur + backup avant reset.

Avant le fix, POST /api/v1/admin/reset/* effacait tout sans rien attendre
dans le corps de la requete (prouve par DAST : 200 + wipe total, curl nu).
"""

from __future__ import annotations

import io


def _upload(client, filename: str, payload: bytes):
    return client.post(
        "/api/v1/documents",
        files={"files": (filename, io.BytesIO(payload), "text/plain")},
    )


def test_reset_without_confirm_body_is_rejected(client) -> None:
    r = client.post("/api/v1/admin/reset/documents", json={})
    assert r.status_code == 422, r.text  # `confirm` manquant (Pydantic).


def test_reset_with_wrong_confirm_token_is_rejected(client) -> None:
    r = client.post("/api/v1/admin/reset/documents", json={"confirm": "sessions"})
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["code"] == "CONFIRMATION_REQUIRED"


def test_reset_documents_with_correct_confirm_deletes_and_backs_up(client) -> None:
    _upload(client, "note.txt", b"contenu de test")
    assert len(client.get("/api/v1/documents").json()) == 1

    r = client.post("/api/v1/admin/reset/documents", json={"confirm": "documents"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scope"] == "documents"
    assert body["deleted"]["documents"] == 1
    # SQLite -> backup toujours produit (DATABASE_URL de test est sqlite:///...).
    assert body["backup_path"]
    assert client.get("/api/v1/documents").json() == []


def test_reset_all_requires_its_own_scope_token(client) -> None:
    r = client.post("/api/v1/admin/reset/all", json={"confirm": "documents"})
    assert r.status_code == 400, r.text
    r2 = client.post("/api/v1/admin/reset/all", json={"confirm": "all"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["scope"] == "all"
