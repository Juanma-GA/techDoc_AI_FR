"""GET /documents/{id}/commented.pdf — le livrable relecteur (PDF annote)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _upload(client: TestClient, sample_pdf_bytes: bytes) -> str:
    resp = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


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


def test_pdf_exports_contract(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc_id = _upload(client, sample_pdf_bytes)
    exports = client.get(f"/api/v1/documents/{doc_id}/exports")
    assert exports.status_code == 200
    payload = exports.json()
    assert payload["source_format"] == "pdf"
    assert payload["working_format"] == "pdf"
    assert {item["kind"] for item in payload["available"]} == {"original", "commented"}
