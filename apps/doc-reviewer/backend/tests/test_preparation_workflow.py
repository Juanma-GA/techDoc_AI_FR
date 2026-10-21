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


def _readable_and_blank_pdf() -> bytes:
    pdf = fitz.open()
    _add_readable_page(pdf)
    pdf.new_page(width=400, height=600)
    data = pdf.tobytes()
    pdf.close()
    return data


def _readable_pdf() -> bytes:
    pdf = fitz.open()
    _add_readable_page(pdf)
    data = pdf.tobytes()
    pdf.close()
    return data


def _add_readable_page(pdf: fitz.Document) -> None:
    page = pdf.new_page(width=400, height=600)
    for line in range(6):
        page.insert_text(
            (40, 60 + line * 24),
            f"Readable native text on this page with enough detail for extraction check {line}.",
            fontsize=10,
        )


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
    assert body["pages"][0]["needs_ocr"] is True
    assert body["pages"][0]["native_text_usable"] is False
    assert body["preparation_rule_count"] == 2
    assert body["checklist_imported_rule_count"] == 0


def test_detection_requires_ocr_for_short_native_text(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    document_id = _upload_document(client, sample_pdf_bytes)

    response = client.post(f"/api/v1/documents/{document_id}/preparation/detect")

    assert response.status_code == 409
    assert response.json()["code"] == "OCR_VALIDATION_REQUIRED"
    assert response.json()["detail"]["pages"] == [1]


def test_readability_preflight_marks_only_weak_pages_for_ocr(client: TestClient) -> None:
    document_id = _upload_document(client, _readable_and_blank_pdf())

    state = client.get(f"/api/v1/documents/{document_id}/preparation").json()
    assert state["pages"][0]["native_text_usable"] is True
    assert state["pages"][0]["needs_ocr"] is False
    assert state["pages"][1]["needs_ocr"] is True

    response = client.post(f"/api/v1/documents/{document_id}/preparation/detect")

    assert response.status_code == 409
    assert response.json()["code"] == "OCR_VALIDATION_REQUIRED"
    assert response.json()["detail"]["pages"] == [2]


def test_detection_runs_without_ocr_when_all_pages_have_usable_native_text(
    client: TestClient,
) -> None:
    document_id = _upload_document(client, _readable_pdf())

    state = client.get(f"/api/v1/documents/{document_id}/preparation").json()
    assert state["pages"][0]["needs_ocr"] is False

    response = client.post(f"/api/v1/documents/{document_id}/preparation/detect")

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1


def test_detection_requires_mistral_validation_for_scanned_pages(client: TestClient) -> None:
    document_id = _upload_document(client, _blank_pdf())

    response = client.post(f"/api/v1/documents/{document_id}/preparation/detect")

    assert response.status_code == 409
    assert response.json()["code"] == "OCR_VALIDATION_REQUIRED"
    assert response.json()["detail"]["pages"] == [1]


def test_document_ocr_processes_only_pages_marked_for_ocr_and_requires_validation(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.core import preparation_ocr_service
    from app.core.ocr_types import OcrBox, OcrPageResult

    document_id = _upload_document(client, _readable_and_blank_pdf())
    calls = []

    def fake_run_ocr(provider, _image_bytes, _width, _height, _db):
        calls.append(provider)
        return OcrPageResult(
            text=f"Synthetic OCR page {len(calls)}",
            boxes=[OcrBox(0.1, 0.1, 0.5, 0.2, f"Synthetic OCR page {len(calls)}")],
            provider=provider,
            elapsed_ms=1234,
        )

    monkeypatch.setattr(preparation_ocr_service, "run_ocr", fake_run_ocr)

    missing_validation = client.post(
        f"/api/v1/documents/{document_id}/preparation/ocr/validation"
    )
    assert missing_validation.status_code == 409
    assert missing_validation.json()["code"] == "OCR_RESULTS_INCOMPLETE"
    assert missing_validation.json()["detail"]["pages"] == [2]

    ocr = client.post(f"/api/v1/documents/{document_id}/preparation/ocr")
    assert ocr.status_code == 200, ocr.text
    assert ocr.json() == {"provider": "mistral", "page_count": 1, "elapsed_ms": 1234}
    assert calls == ["mistral"]

    state = client.get(f"/api/v1/documents/{document_id}/preparation").json()
    assert state["selected_provider"] == "mistral"
    assert state["validated_pages"] == []
    assert state["ocr_results_available"] == [
        {"provider": "mistral", "page": 2},
    ]

    blocked = client.post(f"/api/v1/documents/{document_id}/preparation/detect")
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "OCR_VALIDATION_REQUIRED"
    assert blocked.json()["detail"]["pages"] == [2]

    validated = client.post(
        f"/api/v1/documents/{document_id}/preparation/ocr/validation"
    )
    assert validated.status_code == 200, validated.text
    assert validated.json() == {"provider": "mistral", "validated_pages": [2]}

    detected = client.post(f"/api/v1/documents/{document_id}/preparation/detect")
    assert detected.status_code == 200, detected.text
    assert len(detected.json()) == 2


def test_native_page_text_endpoint_returns_only_pages_using_the_text_layer(
    client: TestClient,
) -> None:
    document_id = _upload_document(client, _readable_and_blank_pdf())

    native_text = client.get(
        f"/api/v1/documents/{document_id}/preparation/text/pages/1"
    )
    scanned_text = client.get(
        f"/api/v1/documents/{document_id}/preparation/text/pages/2"
    )

    assert native_text.status_code == 200, native_text.text
    assert "Readable native text" in native_text.json()["text"]
    assert scanned_text.status_code == 409
    assert scanned_text.json()["code"] == "NATIVE_TEXT_UNAVAILABLE"


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
