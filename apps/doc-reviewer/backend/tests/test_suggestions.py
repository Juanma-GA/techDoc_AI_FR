"""Suggestions API — patch / bulk-status / apply / idempotence."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.db.models import Document, Suggestion
from app.db.session import SessionLocal


def _seed_document_and_suggestion(sample_pdf_bytes: bytes) -> tuple[uuid.UUID, uuid.UUID]:
    """Bypass the SSE pipeline and seed one document + one open suggestion."""
    from app.core.pdf_versioning import init_storage
    from app.core.versioning import sha256_of_bytes

    doc_id = uuid.uuid4()
    storage = f"document_{doc_id.hex}"
    init_storage(storage, sample_pdf_bytes)

    db = SessionLocal()
    try:
        doc = Document(
            id=doc_id,
            original_filename="manual.pdf",
            sha256=sha256_of_bytes(sample_pdf_bytes),
            storage_dir=storage,
            page_count=1,
            target_unit_system="imperial",
            status="analyzed",
            current_version=0,
        )
        db.add(doc)
        sug = Suggestion(
            document_id=doc_id,
            run_id=None,
            rule_kind="units",
            rule_code="UNITS_CONVERT",
            severity="info",
            message="Conversion vers imperial",
            original_text="12 cm",
            proposed_text="4.72 in",
            page=1,
            bbox=json.dumps({"x0": 0.0, "y0": 0.0, "x1": 400.0, "y1": 300.0}),
            span_index=0,
            status="open",
        )
        db.add(sug)
        db.commit()
        db.refresh(sug)
        return doc_id, sug.id
    finally:
        db.close()


def test_patch_status_open_to_accepted(client: TestClient, sample_pdf_bytes: bytes) -> None:
    _, sid = _seed_document_and_suggestion(sample_pdf_bytes)
    resp = client.patch(f"/api/v1/suggestions/{sid}", json={"status": "accepted"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "accepted"


def test_apply_then_idempotent_409(client: TestClient, sample_pdf_bytes: bytes) -> None:
    _, sid = _seed_document_and_suggestion(sample_pdf_bytes)
    client.patch(f"/api/v1/suggestions/{sid}", json={"status": "accepted"})
    first = client.post(f"/api/v1/suggestions/{sid}/apply")
    assert first.status_code == 200, first.text
    assert first.json()["new_version"] == 1

    second = client.post(f"/api/v1/suggestions/{sid}/apply")
    assert second.status_code == 409
    assert second.json()["code"] == "SUGGESTION_ALREADY_APPLIED"


def test_apply_increments_document_version(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc_id, sid = _seed_document_and_suggestion(sample_pdf_bytes)
    client.post(f"/api/v1/suggestions/{sid}/apply")
    doc_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert doc_resp.json()["current_version"] == 1


def test_bulk_status_updates_many(client: TestClient, sample_pdf_bytes: bytes) -> None:
    _, sid = _seed_document_and_suggestion(sample_pdf_bytes)
    resp = client.post(
        "/api/v1/suggestions/bulk-status",
        json={"ids": [str(sid)], "status": "rejected"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1


def test_revert_brings_version_back(client: TestClient, sample_pdf_bytes: bytes) -> None:
    doc_id, sid = _seed_document_and_suggestion(sample_pdf_bytes)
    client.post(f"/api/v1/suggestions/{sid}/apply")
    revert = client.post(f"/api/v1/suggestions/{sid}/revert")
    assert revert.status_code == 200, revert.text
    doc_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert doc_resp.json()["current_version"] == 0
