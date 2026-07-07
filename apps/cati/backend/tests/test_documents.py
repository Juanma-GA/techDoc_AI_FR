"""Tests routes /api/v1/documents - upload, extraction, dedup, CRUD."""

from __future__ import annotations


def _upload(client, pdf_bytes: bytes, name: str = "plan.pdf"):
    return client.post(
        "/api/v1/documents",
        files=[("files", (name, pdf_bytes, "application/pdf"))],
    )


def test_upload_extracts_items(client, cati_pdf_bytes) -> None:
    resp = _upload(client, cati_pdf_bytes)
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["status"] == "created"
    assert result["item_count"] == 2  # 2 articles dans le PDF synthetique
    assert result["document_id"]


def test_upload_rejects_non_pdf(client) -> None:
    resp = client.post(
        "/api/v1/documents",
        files=[("files", ("data.txt", b"hello", "text/plain"))],
    )
    assert resp.status_code == 200
    assert resp.json()["results"][0]["status"] == "error"


def test_upload_dedup_sha256(client, cati_pdf_bytes) -> None:
    first = _upload(client, cati_pdf_bytes).json()["results"][0]
    second = _upload(client, cati_pdf_bytes).json()["results"][0]
    assert second["status"] == "duplicate"
    assert second["document_id"] == first["document_id"]


def test_list_get_and_delete(client, cati_pdf_bytes) -> None:
    doc_id = _upload(client, cati_pdf_bytes).json()["results"][0]["document_id"]

    listed = client.get("/api/v1/documents").json()
    assert any(d["id"] == doc_id for d in listed)

    got = client.get(f"/api/v1/documents/{doc_id}").json()
    assert got["item_count"] == 2
    assert got["status"] == "extracted"

    deleted = client.delete(f"/api/v1/documents/{doc_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/documents/{doc_id}").status_code == 404


def test_get_items_and_header_meta(client, cati_pdf_bytes) -> None:
    doc_id = _upload(client, cati_pdf_bytes).json()["results"][0]["document_id"]

    items = client.get(f"/api/v1/documents/{doc_id}/items").json()
    assert items["method"] == "deterministic"
    assert len(items["items"]) == 2
    assert items["items"][0]["fields"]["fig"] == "10A"

    resp = client.put(
        f"/api/v1/documents/{doc_id}/header-meta",
        json={"module": "F1-PL", "otan_supplier": "NOM FRN"},
    )
    assert resp.status_code == 200
    assert resp.json()["header_meta"]["module"] == "F1-PL"
