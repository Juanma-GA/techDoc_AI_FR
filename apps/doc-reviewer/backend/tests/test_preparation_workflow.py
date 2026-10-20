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


def _two_page_pdf() -> bytes:
    pdf = fitz.open()
    for page_number in (1, 2):
        page = pdf.new_page(width=400, height=300)
        page.insert_text((40, 80), f"Synthetic page {page_number}")
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
    assert body["preparation_rule_count"] == 2
    assert body["checklist_imported_rule_count"] == 0


def test_detection_requires_mistral_validation_even_with_native_text(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    document_id = _upload_document(client, sample_pdf_bytes)

    response = client.post(f"/api/v1/documents/{document_id}/preparation/detect")

    assert response.status_code == 409
    assert response.json()["code"] == "OCR_VALIDATION_REQUIRED"
    assert response.json()["detail"]["pages"] == [1]


def test_detection_requires_mistral_validation_for_scanned_pages(client: TestClient) -> None:
    document_id = _upload_document(client, _blank_pdf())

    response = client.post(f"/api/v1/documents/{document_id}/preparation/detect")

    assert response.status_code == 409
    assert response.json()["code"] == "OCR_VALIDATION_REQUIRED"
    assert response.json()["detail"]["pages"] == [1]


def test_document_ocr_batches_every_page_and_requires_each_validation(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.core import preparation_ocr_service

    document_id = _upload_document(client, _two_page_pdf())
    synthetic_response = {
        "pages": [
            {
                "markdown": f"Synthetic OCR page {page_number}",
                "dimensions": {"width": 800, "height": 600},
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": f"Synthetic OCR page {page_number}",
                        "top_left_x": 20,
                        "top_left_y": 20,
                        "bottom_right_x": 200,
                        "bottom_right_y": 50,
                    }
                ],
            }
            for page_number in (1, 2)
        ]
    }
    monkeypatch.setattr(
        preparation_ocr_service,
        "run_mistral_ocr_document",
        lambda _pdf_bytes, _db: (synthetic_response, 1234),
    )

    ocr = client.post(f"/api/v1/documents/{document_id}/preparation/ocr")
    assert ocr.status_code == 200, ocr.text
    assert ocr.json() == {"provider": "mistral", "page_count": 2, "elapsed_ms": 1234}

    state = client.get(f"/api/v1/documents/{document_id}/preparation").json()
    assert state["selected_provider"] == "mistral"
    assert state["validated_pages"] == []
    assert state["ocr_results_available"] == [
        {"provider": "mistral", "page": 1},
        {"provider": "mistral", "page": 2},
    ]

    blocked = client.post(f"/api/v1/documents/{document_id}/preparation/detect")
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "OCR_VALIDATION_REQUIRED"
    assert blocked.json()["detail"]["pages"] == [1, 2]

    for page_number in (1, 2):
        validated = client.patch(
            f"/api/v1/documents/{document_id}/preparation/ocr/pages/{page_number}/validation",
            json={"provider": "mistral", "validated": True},
        )
        assert validated.status_code == 200, validated.text

    detected = client.post(f"/api/v1/documents/{document_id}/preparation/detect")
    assert detected.status_code == 200, detected.text
    assert len(detected.json()) == 2


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
