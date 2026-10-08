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
    assert body["client_metadata"]["meta_manufacturer"] == body["meta_manufacturer"]


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


def test_patch_document_context_validates_language(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc = _upload(client, sample_pdf_bytes)
    response = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={
            "meta_cmm_number": "24-09-06",
            "meta_revision_date": "MAR 18/26",
            "meta_revision_number": "04",
            "meta_manufacturer": "Boeing",
            "document_language": "en",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_language"] == "en"
    assert body["meta_manufacturer"] == "Boeing"
    assert body["client_metadata"]["meta_cmm_number"] == "24-09-06"
    assert body["client_metadata"]["document_language"] == "en"

    invalid = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"document_language": "de"},
    )
    assert invalid.status_code == 422

    invalid_manufacturer = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"meta_manufacturer": "Embraer"},
    )
    assert invalid_manufacturer.status_code == 422


def test_client_metadata_patch_merges_and_updates_legacy_fields(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    doc = _upload(client, sample_pdf_bytes)
    first = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={
            "client_metadata": {
                "meta_cmm_number": "79-30-02",
                "document_language": "fr",
            }
        },
    )

    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["meta_cmm_number"] == "79-30-02"
    assert first_body["document_language"] == "fr"

    second = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"client_metadata": {"meta_revision_date": "MAR 18/26"}},
    )

    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["client_metadata"]["meta_cmm_number"] == "79-30-02"
    assert second_body["client_metadata"]["document_language"] == "fr"
    assert second_body["client_metadata"]["meta_revision_date"] == "MAR 18/26"
    assert second_body["meta_revision_date"] == "MAR 18/26"


def test_client_metadata_patch_validates_manifest_fields(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    doc = _upload(client, sample_pdf_bytes)
    response = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"client_metadata": {"unknown_field": "value"}},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "CLIENT_METADATA_INVALID"

    invalid_value = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"client_metadata": {"meta_manufacturer": "Embraer"}},
    )
    assert invalid_value.status_code == 422
    assert invalid_value.json()["code"] == "CLIENT_METADATA_INVALID"

    invalid_format = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"client_metadata": {"meta_cmm_number": "7930-02"}},
    )
    assert invalid_format.status_code == 422
    assert invalid_format.json()["code"] == "CLIENT_METADATA_INVALID"


def test_client_metadata_supports_multiple_pnr_values(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    doc = _upload(client, sample_pdf_bytes)
    pnr_values = ["1-879-SB", "2-410-MX"]

    patched = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"client_metadata": {"meta_pnr_number": pnr_values}},
    )

    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["client_metadata"]["meta_pnr_number"] == pnr_values
    assert body["meta_pnr_number"] == ", ".join(pnr_values)

    next_upload = _upload(client, sample_pdf_bytes)
    assert next_upload["client_metadata"]["meta_pnr_number"] == pnr_values
    assert next_upload["meta_pnr_number"] == ", ".join(pnr_values)


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
