"""GET /documents/{id}/commented.pdf — le livrable relecteur (PDF annote)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _upload(client: TestClient, sample_pdf_bytes: bytes) -> str:
    resp = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    document_id = resp.json()["id"]
    context = client.patch(
        f"/api/v1/documents/{document_id}",
        json={
            "meta_revision_date": "JUL 27/26",
            "meta_cmm_number": "79-30-02",
            "meta_first_issue_date": "JUL 1966",
            "meta_revision_number": "Rev. 01",
            "meta_pnr_number": "1-900-SB",
            "document_language": "en",
        },
    )
    assert context.status_code == 200, context.text
    return document_id


def test_commented_pdf_without_findings(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc_id = _upload(client, sample_pdf_bytes)
    resp = client.get(f"/api/v1/documents/{doc_id}/commented.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"  # PDF valide (au moins la page-sommaire)


def test_commented_pdf_after_analyze(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc_id = _upload(client, sample_pdf_bytes)
    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze") as stream:
        assert stream.status_code == 200
        b"".join(stream.iter_bytes())
    resp = client.get(f"/api/v1/documents/{doc_id}/commented.pdf")
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


def test_pdf_exports_contract(
    client: TestClient, sample_pdf_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import doc_convert

    monkeypatch.setattr(doc_convert, "can_convert_formats", lambda: False)
    doc_id = _upload(client, sample_pdf_bytes)
    exports = client.get(f"/api/v1/documents/{doc_id}/exports")
    assert exports.status_code == 200
    payload = exports.json()
    assert payload["source_format"] == "pdf"
    assert payload["working_format"] == "pdf"
    assert {item["kind"] for item in payload["available"]} == {"original", "commented"}
    assert all("warning" in item for item in payload["available"])


def test_pdf_exports_offer_conversions_when_a_converter_exists(
    client: TestClient, sample_pdf_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import doc_convert

    monkeypatch.setattr(doc_convert, "can_convert_formats", lambda: True)
    doc_id = _upload(client, sample_pdf_bytes)
    payload = client.get(f"/api/v1/documents/{doc_id}/exports").json()
    converted = {item["format"] for item in payload["available"] if item["kind"] == "converted"}
    assert converted == {"docx", "doc"}
    assert all(item["warning"] for item in payload["available"] if item["kind"] == "converted")
