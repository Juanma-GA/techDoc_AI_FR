"""Routes /api/v1/documents — upload TXT, list, delete, dedup sha256.

Pas de Mistral configuré : on vérifie que l'upload réussit quand même
(parsing OK, index marqué en erreur)."""

from __future__ import annotations

import io


def _upload(client, filename: str, payload: bytes):
    return client.post(
        "/api/v1/documents",
        files={"files": (filename, io.BytesIO(payload), "text/plain")},
    )


def test_upload_then_list_and_delete(client) -> None:
    r = _upload(client, "note.txt", b"contenu de test pour doc-writer")
    assert r.status_code == 200, r.text
    items = r.json()["uploaded"]
    assert len(items) == 1
    item = items[0]
    assert item["ok"] is True
    assert item["filename"] == "note.txt"
    doc_id = item["document_id"]

    # list
    r2 = client.get("/api/v1/documents")
    assert r2.status_code == 200
    docs = r2.json()
    assert len(docs) == 1
    assert docs[0]["filename"] == "note.txt"
    assert docs[0]["sha256"]
    # Pas de Mistral configuré → index_error renseigné
    assert docs[0]["index_error"] == "MISTRAL_NOT_CONFIGURED"

    # delete
    r3 = client.delete(f"/api/v1/documents/{doc_id}")
    assert r3.status_code == 204
    assert client.get("/api/v1/documents").json() == []


def test_upload_dedup_on_sha256(client) -> None:
    payload = b"identique"
    r1 = _upload(client, "a.txt", payload)
    assert r1.status_code == 200
    r2 = _upload(client, "b.txt", payload)
    assert r2.status_code == 200
    assert r2.json()["uploaded"][0]["skipped"] == "duplicate"

    docs = client.get("/api/v1/documents").json()
    assert len(docs) == 1


def test_upload_rejects_unsupported_extension(client) -> None:
    r = _upload(client, "evil.exe", b"binary garbage")
    assert r.status_code == 200
    item = r.json()["uploaded"][0]
    assert item["ok"] is False
    assert "extension" in (item["error"] or "").lower() or "autorisée" in (item["error"] or "").lower()


def test_delete_unknown_document_returns_404(client) -> None:
    r = client.delete("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "DOCUMENT_NOT_FOUND"
