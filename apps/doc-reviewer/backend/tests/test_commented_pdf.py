"""GET /documents/{id}/commented.pdf — le livrable relecteur (PDF annote)."""

from __future__ import annotations

import json
import uuid

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.pdf_annotate import (
    MissingPageRepair,
    PreparationRepairRule,
    build_commented_pdf,
)
from app.core.preparation_classification import (
    preparation_rules,
    required_page_type_groups,
)
from app.db.preparation_models import DocumentPreparation
from app.db.session import SessionLocal


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


def test_commented_pdf_appends_preparation_repair_details(tmp_path) -> None:
    source = fitz.open()
    source.new_page()
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(source.tobytes())
    source.close()

    content = build_commented_pdf(
        pdf_path,
        [],
        preparation_repairs=(
            MissingPageRepair(
                page_types=("TP1",),
                rules=(
                    PreparationRepairRule(
                        title="Vérifier la page de titre",
                        instructions=("Ajouter le numéro et le titre du document.",),
                    ),
                ),
            ),
        ),
    )
    pdf = fitz.open(stream=content, filetype="pdf")
    try:
        assert pdf.page_count == 3
        appendix = pdf[-1].get_text()
        assert "Annexe de préparation" in appendix
        assert "TP1" in appendix
        assert "Vérifier la page de titre" in appendix
        assert "Ajouter le numéro et le titre du document." in appendix
    finally:
        pdf.close()


def test_commented_pdf_paginates_long_preparation_repairs(tmp_path) -> None:
    source = fitz.open()
    source.new_page()
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(source.tobytes())
    source.close()
    rules = tuple(
        PreparationRepairRule(
            title=f"Règle {index}",
            instructions=(f"Consigne de réparation numéro {index}.",),
        )
        for index in range(40)
    )

    content = build_commented_pdf(
        pdf_path,
        [],
        preparation_repairs=(
            MissingPageRepair(page_types=("TP1",), rules=rules),
        ),
    )
    pdf = fitz.open(stream=content, filetype="pdf")
    try:
        assert pdf.page_count > 3
        assert "Consigne de réparation numéro 39." in "\n".join(
            page.get_text() for page in pdf
        )
    finally:
        pdf.close()


def test_commented_pdf_includes_declared_absent_preparation_pages(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    doc_id = _upload(client, sample_pdf_bytes)
    preparation = client.get(f"/api/v1/documents/{doc_id}/preparation")
    assert preparation.status_code == 200, preparation.text

    with SessionLocal() as db:
        configuration = client.app.state.client_configuration
        rules = preparation_rules(db, configuration.bundle)
        group = required_page_type_groups(rules)[0]
        record = db.scalar(
            select(DocumentPreparation).where(
                DocumentPreparation.document_id == uuid.UUID(doc_id),
            )
        )
        assert record is not None
        record.page_decisions_json = json.dumps([{"page": 1, "page_type": None}])
        record.absent_page_types_json = json.dumps(group)
        db.commit()

    response = client.get(f"/api/v1/documents/{doc_id}/commented.pdf")
    assert response.status_code == 200, response.text
    pdf = fitz.open(stream=response.content, filetype="pdf")
    try:
        text = "\n".join(page.get_text() for page in pdf)
        assert "Annexe de préparation" in text
        assert all(page_type in text for page_type in group)
        assert any(rule.topic in text for rule in rules)
    finally:
        pdf.close()


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
