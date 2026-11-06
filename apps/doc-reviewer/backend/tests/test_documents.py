"""POST /documents — upload, list, get, delete, get_pdf, history."""

from __future__ import annotations

import fitz
from fastapi.testclient import TestClient


def _upload(client: TestClient, sample_pdf_bytes: bytes, target: str = "imperial") -> dict:
    response = client.post(
        f"/api/v1/documents?target={target}",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _pdf_with_text(text: str) -> bytes:
    pdf = fitz.open()
    pdf.new_page().insert_text((50, 50), text)
    data = pdf.tobytes()
    pdf.close()
    return data


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


def test_list_filters_documents_by_workspace(
    client: TestClient, sample_pdf_bytes: bytes
) -> None:
    control = _upload(client, sample_pdf_bytes)
    response = client.post(
        "/api/v1/documents?target=none&workspace=preparation",
        files={"file": ("prep.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    preparation = response.json()
    assert control["workspace"] == "control"
    assert preparation["workspace"] == "preparation"

    control_ids = [d["id"] for d in client.get("/api/v1/documents?workspace=control").json()]
    prep_ids = [d["id"] for d in client.get("/api/v1/documents?workspace=preparation").json()]
    all_ids = [d["id"] for d in client.get("/api/v1/documents").json()]
    assert control["id"] in control_ids and preparation["id"] not in control_ids
    assert preparation["id"] in prep_ids and control["id"] not in prep_ids
    assert {control["id"], preparation["id"]} <= set(all_ids)

    invalid = client.get("/api/v1/documents?workspace=other")
    assert invalid.status_code == 422


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
    valid_cmm_suffix = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"client_metadata": {"meta_cmm_number": "79-30-02A"}},
    )
    assert valid_cmm_suffix.status_code == 200, valid_cmm_suffix.text
    assert valid_cmm_suffix.json()["client_metadata"]["meta_cmm_number"] == "79-30-02A"

    invalid_format = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"client_metadata": {"meta_cmm_number": "7930-02"}},
    )
    assert invalid_format.status_code == 422
    assert invalid_format.json()["code"] == "CLIENT_METADATA_INVALID"


def test_s1000d_first_issue_year_validation_and_defaults_are_norm_scoped(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    document = _upload(client, sample_pdf_bytes)
    valid = client.patch(
        f"/api/v1/documents/{document['id']}?norm=s1000d",
        json={"client_metadata": {"meta_first_issue_date": "2024"}},
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["client_metadata"]["meta_first_issue_date"] == "2024"

    invalid = client.patch(
        f"/api/v1/documents/{document['id']}?norm=s1000d",
        json={"client_metadata": {"meta_first_issue_date": "JUL 25/95"}},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "CLIENT_METADATA_INVALID"

    ata_document = _upload(client, sample_pdf_bytes)
    assert ata_document["client_metadata"].get("meta_first_issue_date") is None

    s1000d_pdf = _pdf_with_text(
        "LIST OF EFFECTIVE DATA MODULES\n"
        "F9111CMON-A-20-02-00-00A-800A-A\n"
        "001-00\n2026-10-30\nStorage - General procedure\nC"
    )
    s1000d_upload = client.post(
        "/api/v1/documents",
        files={"file": ("s1000d.pdf", s1000d_pdf, "application/pdf")},
    )
    assert s1000d_upload.status_code == 201, s1000d_upload.text
    assert s1000d_upload.json()["client_metadata"].get("meta_first_issue_date") == "2024"


def test_clearing_manufacturer_keeps_legacy_column_valid_and_clears_future_mapping(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    document = _upload(client, sample_pdf_bytes)
    response = client.patch(
        f"/api/v1/documents/{document['id']}",
        json={"client_metadata": {"meta_manufacturer": None}},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["client_metadata"]["meta_manufacturer"] is None
    assert body["meta_manufacturer"] in {"Airbus", "Boeing"}

    next_document = _upload(client, sample_pdf_bytes)
    assert next_document["client_metadata"]["meta_manufacturer"] is None
    assert next_document["meta_manufacturer"] == "Airbus"


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


def test_metadata_suggestions_scan_only_four_pages_without_persisting(
    client: TestClient,
) -> None:
    import fitz

    pdf = fitz.open()
    page_texts = [
        "HIGHLIGHTS PAGE 1\nATA No. 80-80-01\nRevision No. 01\nRevision Date: JUL 27/26",
        "TP1\nPart Number: 1-900-SB\nRevision No. 01\nFirst Issue: JUL 25/95",
        "",
        "",
        "TP1\nPart Number: 9-999-ZZ\nFirst Issue: AUG 01/01",
    ]
    for text in page_texts:
        page = pdf.new_page()
        if text:
            page.insert_textbox(
                fitz.Rect(30, 30, 560, 800),
                text,
                fontname="helv",
                fontsize=11,
            )
    pdf_bytes = pdf.tobytes()
    pdf.close()

    document = _upload(client, pdf_bytes)
    before = client.get(f"/api/v1/documents/{document['id']}").json()
    response = client.post(
        f"/api/v1/documents/{document['id']}/metadata-suggestions"
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "pages_scanned": 4,
        "meta_cmm_number": "80-80-01",
        "meta_pnr_number": ["1-900-SB"],
        "meta_revision_number": "01",
        "meta_revision_date": "JUL 27/26",
        "meta_first_issue_date": "JUL 25/95",
    }
    after = client.get(f"/api/v1/documents/{document['id']}").json()
    assert after["client_metadata"] == before["client_metadata"]
    for field in (
        "meta_cmm_number",
        "meta_pnr_number",
        "meta_revision_number",
        "meta_revision_date",
        "meta_first_issue_date",
    ):
        assert after[field] == before[field]


def test_metadata_suggestions_prefers_validated_preparation_ocr(
    client: TestClient,
) -> None:
    import json
    import uuid

    import fitz
    from sqlalchemy import select

    from app.db.preparation_models import DocumentPreparation
    from app.db.session import SessionLocal

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_textbox(
        fitz.Rect(30, 30, 560, 800),
        "HIGHLIGHTS PAGE 1\n"
        "ATA No. 80-80-01\n"
        "Revision No. 01\n"
        "Revision Date: JUL 27/26",
        fontname="helv",
        fontsize=11,
    )
    pdf_bytes = pdf.tobytes()
    pdf.close()

    document = _upload(client, pdf_bytes)
    preparation = client.get(f"/api/v1/documents/{document['id']}/preparation")
    assert preparation.status_code == 200, preparation.text

    session = SessionLocal()
    try:
        record = session.scalar(
            select(DocumentPreparation).where(
                DocumentPreparation.document_id == uuid.UUID(document["id"])
            )
        )
        assert record is not None
        record.ocr_results_json = json.dumps(
            {
                "mistral": {
                    "1": {
                        "text": (
                            "HIGHLIGHTS PAGE 1\n"
                            "ATA No. 90-90-02\n"
                            "Revision No. 04\n"
                            "Revision Date: AUG 14/26"
                        )
                    }
                }
            }
        )
        record.validated_pages_json = json.dumps({"mistral": []})
        session.commit()
    finally:
        session.close()

    response = client.post(
        f"/api/v1/documents/{document['id']}/metadata-suggestions"
    )
    assert response.status_code == 200, response.text
    assert response.json()["meta_cmm_number"] == "80-80-01"

    session = SessionLocal()
    try:
        record = session.scalar(
            select(DocumentPreparation).where(
                DocumentPreparation.document_id == uuid.UUID(document["id"])
            )
        )
        assert record is not None
        record.validated_pages_json = json.dumps({"mistral": [1]})
        session.commit()
    finally:
        session.close()

    response = client.post(
        f"/api/v1/documents/{document['id']}/metadata-suggestions"
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "pages_scanned": 1,
        "meta_cmm_number": "90-90-02",
        "meta_pnr_number": [],
        "meta_revision_number": "04",
        "meta_revision_date": "AUG 14/26",
        "meta_first_issue_date": None,
    }


def test_get_pdf_unknown_version(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc = _upload(client, sample_pdf_bytes)
    resp = client.get(f"/api/v1/documents/{doc['id']}/pdf?version=42")
    assert resp.status_code == 404


def test_delete_removes_document(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc = _upload(client, sample_pdf_bytes)
    del_resp = client.delete(f"/api/v1/documents/{doc['id']}")
    assert del_resp.status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 404
