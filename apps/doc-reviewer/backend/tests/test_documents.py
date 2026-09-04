"""POST /documents — upload, list, get, delete, get_pdf, history."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _upload(client: TestClient, sample_pdf_bytes: bytes, target: str = "imperial") -> dict:
    response = client.post(
        f"/api/v1/documents?target={target}",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_pdf_persists_v0(client: TestClient, sample_pdf_bytes: bytes) -> None:
    body = _upload(client, sample_pdf_bytes)
    assert body["original_filename"] == "manual.pdf"
    assert body["sha256"] and len(body["sha256"]) == 64
    assert body["page_count"] == 1
    assert body["target_unit_system"] == "imperial"
    assert body["status"] == "uploaded"
    assert body["current_version"] == 0


def test_upload_rejects_non_pdf(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("not.pdf", b"hello world", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "UPLOAD_BAD_EXT"


def test_upload_rejects_empty(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "UPLOAD_EMPTY"


def test_list_and_get(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc = _upload(client, sample_pdf_bytes)
    list_resp = client.get("/api/v1/documents")
    assert list_resp.status_code == 200
    ids = [d["id"] for d in list_resp.json()]
    assert doc["id"] in ids

    get_resp = client.get(f"/api/v1/documents/{doc['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == doc["id"]


def test_get_pdf_returns_v0_bytes(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc = _upload(client, sample_pdf_bytes)
    pdf_resp = client.get(f"/api/v1/documents/{doc['id']}/pdf?version=original")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"].startswith("application/pdf")
    assert pdf_resp.content.startswith(b"%PDF-")


def test_get_pdf_unknown_version(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc = _upload(client, sample_pdf_bytes)
    resp = client.get(f"/api/v1/documents/{doc['id']}/pdf?version=42")
    assert resp.status_code == 404


def test_delete_removes_document(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc = _upload(client, sample_pdf_bytes)
    del_resp = client.delete(f"/api/v1/documents/{doc['id']}")
    assert del_resp.status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 404
