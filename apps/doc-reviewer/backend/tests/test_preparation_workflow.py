from __future__ import annotations

import json
import uuid

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select


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
    assert body["preparation_rule_count"] == 14
    assert body["checklist_imported_rule_count"] == 0


def test_preparation_mapping_is_independent_from_verification_mapping(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    document_id = _upload_document(client, sample_pdf_bytes)
    verification_mapping = {
        "meta_revision_date": "JUL 27/26",
        "meta_cmm_number": "79-30-02",
        "meta_first_issue_date": "JUL 1966",
        "meta_revision_number": "01",
        "meta_pnr_number": ["1-900-SB"],
        "meta_manufacturer": "Airbus",
        "document_language": "en",
    }
    document_patch = client.patch(
        f"/api/v1/documents/{document_id}",
        json={"client_metadata": verification_mapping},
    )
    assert document_patch.status_code == 200, document_patch.text

    preparation = client.get(f"/api/v1/documents/{document_id}/preparation")
    assert preparation.status_code == 200, preparation.text
    preparation_mapping = {"meta_cmm_number": "80-80-01"}
    mapping_patch = client.patch(
        f"/api/v1/documents/{document_id}/preparation/mapping",
        json={"mapping": preparation_mapping},
    )
    assert mapping_patch.status_code == 200, mapping_patch.text

    state = client.get(f"/api/v1/documents/{document_id}/preparation")
    document = client.get(f"/api/v1/documents/{document_id}")
    assert state.json()["preparation_mapping"] == preparation_mapping
    assert document.json()["client_metadata"] == verification_mapping

    blocked = client.post(
        f"/api/v1/documents/{document_id}/analyze?preparation_context=true"
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "DOCUMENT_CONTEXT_INCOMPLETE"
    assert set(blocked.json()["detail"]["fields"]) == {
        "meta_revision_date",
        "meta_first_issue_date",
        "meta_revision_number",
        "meta_pnr_number",
    }


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


def test_preparation_review_runs_verification_rules_with_ocr_boxes(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.core import preparation_ocr_service
    from app.core.ocr_types import OcrBox, OcrPageResult
    from app.db.models import AnalysisRun
    from app.db.session import SessionLocal

    client_config = client.get("/api/v1/client-config").json()
    catalogs = client_config["catalogs"]
    thales_catalog = next(catalog for catalog in catalogs if catalog["code"] == "THALES-CUSTOM")
    ste_catalog = next(catalog for catalog in catalogs if catalog["code"] == "ASD-STE100")
    upload = client.post(
        "/api/v1/documents",
        params={
            "target": "imperial",
            "standard_version_ids": ste_catalog["standard_version_id"],
        },
        files={"file": ("current.pdf", _readable_and_blank_pdf(), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    mapping = {
        "meta_revision_date": "AUG 03/26",
        "meta_cmm_number": "79-30-02",
        "meta_first_issue_date": "JUL 1966",
        "meta_revision_number": "02",
        "meta_pnr_number": ["1-900-SB"],
        "meta_manufacturer": "Airbus",
        "document_language": "en",
    }
    mapped = client.patch(
        f"/api/v1/documents/{document_id}/preparation/mapping",
        json={"mapping": mapping},
    )
    assert mapped.status_code == 200, mapped.text

    def fake_run_ocr(provider, _image_bytes, _width, _height, _db):
        return OcrPageResult(
            text="79-33-02\nFirst Issue",
            boxes=[
                OcrBox(0.1, 0.9, 0.4, 0.92, "79-33-02"),
                OcrBox(0.1, 0.93, 0.3, 0.95, "First Issue"),
            ],
            provider=provider,
            elapsed_ms=1234,
        )

    monkeypatch.setattr(preparation_ocr_service, "run_ocr", fake_run_ocr)
    ocr = client.post(
        f"/api/v1/documents/{document_id}/preparation/ocr/pages/2",
        json={"provider": "mistral"},
    )
    assert ocr.status_code == 200, ocr.text
    validated = client.post(
        f"/api/v1/documents/{document_id}/preparation/ocr/validation"
    )
    assert validated.status_code == 200, validated.text
    detected = client.post(f"/api/v1/documents/{document_id}/preparation/detect")
    assert detected.status_code == 200, detected.text
    for page, is_modified in ((1, False), (2, True)):
        decision = client.patch(
            f"/api/v1/documents/{document_id}/preparation/decisions/{page}",
            json={"is_modified": is_modified},
        )
        assert decision.status_code == 200, decision.text

    with client.stream(
        "POST",
        f"/api/v1/documents/{document_id}/analyze",
        params={
            "preparation_context": "true",
            "modified_only": "true",
            "checklist": "false",
            "page_overrides": json.dumps({"1": False, "2": True}),
        },
    ) as stream:
        assert stream.status_code == 200, stream.read().decode("utf-8")
        body = b"".join(stream.iter_bytes())
    assert b"event: done" in body

    all_rules = client.get("/api/v1/client-rules").json()
    verification_rules = [
        rule for rule in all_rules if rule["scope"] == "verification"
    ]
    assert len(verification_rules) > 70
    enabled_verification_codes = {
        rule["code"] for rule in verification_rules if rule["active"]
    }
    disabled_verification_codes = {
        rule["code"] for rule in verification_rules if not rule["active"]
    }
    with SessionLocal() as session:
        run = session.scalar(
            select(AnalysisRun)
            .where(AnalysisRun.document_id == uuid.UUID(document_id))
            .order_by(AnalysisRun.started_at.desc())
            .limit(1)
        )
        assert run is not None
        snapshot = json.loads(run.compiled_rules_snapshot_json)
    compiled_rule_codes = {rule["id"] for rule in snapshot["rules"]}
    assert enabled_verification_codes <= compiled_rule_codes
    assert disabled_verification_codes.isdisjoint(compiled_rule_codes)
    assert thales_catalog["standard_version_id"] in run.standard_version_ids

    rule_results = client.get(
        f"/api/v1/documents/{document_id}/rule-results"
    ).json()
    assert any(
        result["rule_id"] == "CUSTOM_CMM_NUMBER" and result["status"] == "FAIL"
        for result in rule_results
    )
    suggestions = client.get(
        f"/api/v1/documents/{document_id}/suggestions"
    ).json()
    cmm_suggestion = next(
        suggestion
        for suggestion in suggestions
        if suggestion["rule_code"] == "CUSTOM_CMM_NUMBER"
    )
    assert cmm_suggestion["page"] == 2
    assert cmm_suggestion["bbox"]["x0"] == pytest.approx(40)
    assert cmm_suggestion["bbox"]["y0"] == pytest.approx(540)
    assert cmm_suggestion["bbox"]["x1"] == pytest.approx(160)
    assert cmm_suggestion["bbox"]["y1"] == pytest.approx(552)
