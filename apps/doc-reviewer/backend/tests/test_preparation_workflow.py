from __future__ import annotations

import fitz
from fastapi.testclient import TestClient


def _upload_document(client: TestClient, pdf_bytes: bytes) -> str:
    response = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("current.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _blank_pdf() -> bytes:
    pdf = fitz.open()
    pdf.new_page()
    data = pdf.tobytes()
    pdf.close()
    return data


def test_preparation_initializes_from_uploaded_document_without_reference_upload(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    document_id = _upload_document(client, sample_pdf_bytes)

    response = client.get(f"/api/v1/documents/{document_id}/preparation")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_filename"] == "current.pdf"
    assert body["page_count"] == 1
    assert body["pages"][0]["native_text_chars"] > 0


def test_detection_without_ocr_provider_when_document_has_native_text(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    document_id = _upload_document(client, sample_pdf_bytes)

    response = client.post(f"/api/v1/documents/{document_id}/preparation/detect")

    assert response.status_code == 409
    assert response.json()["code"] == "PREPARATION_CHECKLIST_MISSING"


def test_detection_requires_ocr_provider_when_document_has_no_native_text(
    client: TestClient,
) -> None:
    document_id = _upload_document(client, _blank_pdf())

    response = client.post(f"/api/v1/documents/{document_id}/preparation/detect")

    assert response.status_code == 409
    assert response.json()["code"] == "OCR_PROVIDER_NOT_SELECTED"


def test_preparation_state_loads_after_provider_selection(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    document_id = _upload_document(client, sample_pdf_bytes)
    selected = client.patch(
        f"/api/v1/documents/{document_id}/preparation/provider",
        json={"provider": "mistral"},
    )
    assert selected.status_code == 200, selected.text

    response = client.get(f"/api/v1/documents/{document_id}/preparation")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["page_count"] == 1
    assert body["validated_pages"] == []
