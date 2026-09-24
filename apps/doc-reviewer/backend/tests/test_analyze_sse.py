"""POST /documents/{id}/analyze — SSE smoke test.

We don't parse the full SSE stream tightly; we just verify the endpoint
returns text/event-stream content and that suggestions are persisted.
"""

from __future__ import annotations

import io
import hashlib
import json
import uuid

from openpyxl import Workbook
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.checks.client_registry import load_active_client_configuration
from app.api import rules as rules_api
from app.core.compiled_rules import Check, CompiledRule, RuleTarget
from app.db.models import AnalysisRun, Document
from app.db.session import SessionLocal


def _set_document_context(client: TestClient, document_id: str) -> None:
    response = client.patch(
        f"/api/v1/documents/{document_id}",
        json={
            "meta_revision_date": "JUL 27/26",
            "meta_cmm_number": "79-30-02",
            "meta_first_issue_date": "JUL 1966",
            "meta_revision_number": "Rev. 01",
            "document_language": "en",
        },
    )
    assert response.status_code == 200, response.text


def test_analyze_requires_complete_document_context(client: TestClient, sample_pdf_bytes: bytes) -> None:
    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    blocked = client.post(f"/api/v1/documents/{doc_id}/analyze")

    assert blocked.status_code == 409
    assert blocked.json()["code"] == "DOCUMENT_CONTEXT_INCOMPLETE"
    assert set(blocked.json()["detail"]["fields"]) == {
        "meta_revision_date",
        "meta_cmm_number",
        "meta_first_issue_date",
        "meta_revision_number",
        "document_language",
    }


def test_analyze_emits_events_and_persists(client: TestClient, sample_pdf_bytes: bytes) -> None:
    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]
    _set_document_context(client, doc_id)

    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze") as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        body = b"".join(stream.iter_bytes())

    assert b"run_started" in body
    assert b"done" in body

    sugs = client.get(f"/api/v1/documents/{doc_id}/suggestions")
    assert sugs.status_code == 200
    rows = sugs.json()
    # At least one units suggestion should pop up because the fixture pdf
    # contains both "12 cm" and "5 in".
    assert any(r["rule_kind"] == "units" for r in rows)


def test_analyze_stores_tp1_page_type_in_context_snapshot(client: TestClient) -> None:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page(width=400, height=300)
    page.insert_text((40, 100), "Title page body", fontname="helv", fontsize=12)
    page.insert_text((40, 240), "Revision: JUL 27/26", fontname="helv", fontsize=8)
    page.insert_text((40, 252), "TP 1", fontname="helv", fontsize=8)
    pdf_bytes = pdf.tobytes()
    pdf.close()

    # La classification TP1 est portée par le bundle THALES actif.
    standards = client.get("/api/v1/standards")
    custom = next(item for item in standards.json() if item["code"] == "THALES-CUSTOM")
    version_id = custom["versions"][0]["id"]

    upload = client.post(
        f"/api/v1/documents?target=imperial&standard_version_ids={version_id}",
        files={"file": ("tp1.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]
    client_configuration = load_active_client_configuration()
    with SessionLocal() as session:
        historical_document = session.get(Document, uuid.UUID(doc_id))
        assert historical_document is not None
        historical_document.standard_version_id = None
        historical_document.standard_version_ids = "[]"
        session.commit()
    _set_document_context(client, doc_id)

    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze") as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes())
    assert b"done" in body

    with SessionLocal() as session:
        run = session.scalar(
            select(AnalysisRun)
            .where(AnalysisRun.document_id == uuid.UUID(doc_id))
            .order_by(AnalysisRun.started_at.desc())
            .limit(1)
        )
        assert run is not None
        snapshot = json.loads(run.context_snapshot_json)
        bundle_snapshot = snapshot["client_bundle"]
        assert bundle_snapshot["bundle"] == client_configuration.selection.bundle
        assert bundle_snapshot["client_code"] == client_configuration.manifest.client_code
        assert bundle_snapshot["bundle_version"] == client_configuration.manifest.bundle_version
        assert bundle_snapshot["contract_version"] == client_configuration.manifest.contract_version
        assert bundle_snapshot["catalogs"] == [
            catalog.model_dump(mode="json")
            for catalog in client_configuration.manifest.catalogs
        ]
        assert bundle_snapshot["manifest_hash"] == client_configuration.manifest_hash
        assert bundle_snapshot["mapping_hash"] == client_configuration.mapping_hash
        assert bundle_snapshot["bundle_hash"] == client_configuration.bundle_hash
        assert snapshot["metadata"]["client_metadata"]["meta_cmm_number"] == "79-30-02"
        assert run.standard_version_id == uuid.UUID(version_id)
        assert json.loads(run.standard_version_ids) == [version_id]
        assert run.snapshot_sha256 == hashlib.sha256(
            f"{run.context_snapshot_json}\n{run.compiled_rules_snapshot_json}".encode("utf-8")
        ).hexdigest()
        historical_document = session.get(Document, uuid.UUID(doc_id))
        assert historical_document is not None
        assert historical_document.standard_version_id is None
        assert json.loads(historical_document.standard_version_ids) == []

    assert snapshot["page_types"] == {"1": "TP1"}


def test_reanalysis_warns_when_previous_bundle_is_unavailable(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    _set_document_context(client, document_id)

    with client.stream("POST", f"/api/v1/documents/{document_id}/analyze") as stream:
        assert stream.status_code == 200
        first_body = b"".join(stream.iter_bytes())
    assert b"done" in first_body

    with SessionLocal() as session:
        previous_run = session.scalar(
            select(AnalysisRun)
            .where(AnalysisRun.document_id == uuid.UUID(document_id))
            .order_by(AnalysisRun.started_at.desc())
            .limit(1)
        )
        assert previous_run is not None
        previous_snapshot = json.loads(previous_run.context_snapshot_json)
        previous_snapshot["client_bundle"]["bundle_hash"] = "unavailable-previous-bundle"
        previous_run.context_snapshot_json = json.dumps(previous_snapshot)
        session.commit()

    with client.stream("POST", f"/api/v1/documents/{document_id}/analyze") as stream:
        assert stream.status_code == 200
        second_body = b"".join(stream.iter_bytes())
    assert b"bundle actif" in second_body

    with SessionLocal() as session:
        current_run = session.scalar(
            select(AnalysisRun)
            .where(AnalysisRun.document_id == uuid.UUID(document_id))
            .order_by(AnalysisRun.started_at.desc())
            .limit(1)
        )
        assert current_run is not None
        reanalysis = json.loads(current_run.context_snapshot_json)["client_bundle"]["reanalysis"]
        assert reanalysis == {
            "previous_bundle_hash": "unavailable-previous-bundle",
            "using_current_bundle": True,
        }


def test_imported_compiled_rule_comments_matching_pdf_text(
    client: TestClient,
    sample_pdf_bytes: bytes,
    monkeypatch,
) -> None:
    workbook = Workbook()
    workbook.active.append(["Topic", "Check"])
    workbook.active.append(["Torque", "The document must not contain 12 cm."])
    checklist = io.BytesIO()
    workbook.save(checklist)

    def compile_rule(_db, row, filename: str, *, client_bundle=None) -> CompiledRule:
        return CompiledRule(
            id=f"compiled-{row.row_number}",
            topic=row.category,
            execution="deterministic",
            target=RuleTarget(page="all", region="full_page"),
            checks=[Check(field="text", operator="regex", expected=r"12 cm")],
            source="user_checklist",
            origin_ref=f"{filename}:{row.sheet}:{row.row_number}",
        )

    monkeypatch.setattr(rules_api, "compile_checklist_rule", compile_rule)
    imported = client.post(
        "/api/v1/rules/import",
        files={"file": ("checklist.xlsx", checklist.getvalue(), "application/vnd.ms-excel")},
        data={"mode": "replace"},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["rules"][0]["active"] is True

    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]
    _set_document_context(client, doc_id)

    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze?checklist=true") as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes())
    assert b"done" in body

    suggestions = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    assert any(
        row["rule_code"] == "compiled-2" and row["original_text"] == "12 cm"
        for row in suggestions
    )
