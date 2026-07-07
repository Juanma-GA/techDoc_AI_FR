"""Tests routes /api/v1/documents/{id}/items - edition des lignes."""

from __future__ import annotations


def _upload(client, pdf_bytes: bytes) -> str:
    resp = client.post(
        "/api/v1/documents",
        files=[("files", ("plan.pdf", pdf_bytes, "application/pdf"))],
    )
    return resp.json()["results"][0]["document_id"]


def test_patch_item_marks_edited(client, cati_pdf_bytes) -> None:
    doc_id = _upload(client, cati_pdf_bytes)
    items = client.get(f"/api/v1/documents/{doc_id}/items").json()["items"]
    item_id = items[0]["id"]

    resp = client.patch(
        f"/api/v1/documents/{doc_id}/items/{item_id}",
        json={"fields": {"description": "Corrige"}, "included": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fields"]["description"] == "Corrige"
    assert body["fields"]["fig"] == "10A"  # champs non touches preserves
    assert body["included"] is False
    assert body["edited"] is True


def test_create_and_delete_item(client, cati_pdf_bytes) -> None:
    doc_id = _upload(client, cati_pdf_bytes)

    created = client.post(
        f"/api/v1/documents/{doc_id}/items",
        json={"fields": {"fig": "99A", "description": "Ajout"}},
    ).json()
    assert created["fields"]["fig"] == "99A"

    items = client.get(f"/api/v1/documents/{doc_id}/items").json()["items"]
    assert len(items) == 3

    resp = client.delete(f"/api/v1/documents/{doc_id}/items/{created['id']}")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


def test_reorder_items(client, cati_pdf_bytes) -> None:
    doc_id = _upload(client, cati_pdf_bytes)
    items = client.get(f"/api/v1/documents/{doc_id}/items").json()["items"]
    ids = [it["id"] for it in items]

    reordered = client.post(
        f"/api/v1/documents/{doc_id}/items/reorder",
        json={"ordered_ids": list(reversed(ids))},
    ).json()["items"]
    assert [it["id"] for it in reordered] == list(reversed(ids))
