"""Document context defaults are persisted and copied to new uploads."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_document_context_is_reused_for_next_upload(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    first = client.post(
        "/api/v1/documents",
        files={"file": ("first.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert first.status_code == 201, first.text
    assert first.json()["meta_revision_date"] is None
    assert first.json()["document_language"] is None

    context = {
        "meta_revision_date": "JUL 27/26",
        "meta_cmm_number": "79-30-02",
        "meta_first_issue_date": "JUL 1966",
        "meta_revision_number": "Rev. 01",
        "meta_pnr_number": "1-879-SB",
        "document_language": "en",
    }
    patched = client.patch(
        f"/api/v1/documents/{first.json()['id']}",
        json=context,
    )
    assert patched.status_code == 200, patched.text

    second = client.post(
        "/api/v1/documents",
        files={"file": ("second.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert second.status_code == 201, second.text
    second_body = second.json()
    assert {field: second_body[field] for field in context} == context
