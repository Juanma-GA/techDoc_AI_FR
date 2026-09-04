"""Suggestions API — grouped apply across every page of a document."""

from __future__ import annotations

import json
import uuid

import fitz
from fastapi.testclient import TestClient

from app.db.models import Document, Suggestion
from app.db.session import SessionLocal


def _make_multipage_pdf(text: str, pages: int) -> bytes:
    """Build a PDF carrying the same text on every page."""
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=400, height=300)
        page.insert_text((50, 100), text, fontname="helv", fontsize=12)
    raw = doc.tobytes()
    doc.close()
    return raw


def _seed_group(pages: int) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Seed one document with the SAME anomaly (identical rule_code +
    original_text + proposed_text) on `pages` distinct pages."""
    from app.core.pdf_versioning import init_storage
    from app.core.versioning import sha256_of_bytes

    raw = _make_multipage_pdf("Torque 12 cm here", pages)
    doc_id = uuid.uuid4()
    storage = f"document_{doc_id.hex}"
    init_storage(storage, raw)

    db = SessionLocal()
    try:
        db.add(
            Document(
                id=doc_id,
                original_filename="manual.pdf",
                sha256=sha256_of_bytes(raw),
                storage_dir=storage,
                page_count=pages,
                target_unit_system="imperial",
                status="analyzed",
                current_version=0,
            )
        )
        ids: list[uuid.UUID] = []
        for page in range(1, pages + 1):
            sug = Suggestion(
                document_id=doc_id,
                rule_kind="units",
                rule_code="UNITS_CONVERT",
                severity="info",
                message="Conversion vers imperial",
                original_text="12 cm",
                proposed_text="4.72 in",
                page=page,
                bbox=json.dumps({"x0": 0.0, "y0": 0.0, "x1": 400.0, "y1": 300.0}),
                span_index=0,
                status="open",
            )
            db.add(sug)
            db.flush()
            ids.append(sug.id)
        db.commit()
        return doc_id, ids
    finally:
        db.close()


def test_apply_group_patches_every_page(client: TestClient) -> None:
    doc_id, ids = _seed_group(pages=3)
    resp = client.post(f"/api/v1/suggestions/{ids[0]}/apply-group")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["applied_count"] == 3
    assert body["skipped_count"] == 0
    assert sorted(body["pages"]) == [1, 2, 3]
    assert set(body["applied_ids"]) == {str(i) for i in ids}

    # Document version bumped once per applied suggestion.
    doc_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert doc_resp.json()["current_version"] == 3

    # Every group member is now `applied`.
    for sid in ids:
        s = client.get(f"/api/v1/suggestions/{sid}").json()
        assert s["status"] == "applied"


def test_apply_group_ignores_unrelated_suggestions(client: TestClient) -> None:
    doc_id, ids = _seed_group(pages=2)
    # Add an unrelated suggestion on page 1 — different rule + text.
    db = SessionLocal()
    try:
        other = Suggestion(
            document_id=doc_id,
            rule_kind="units",
            rule_code="UNITS_CONVERT",
            severity="info",
            message="Autre conversion",
            original_text="5 mm",
            proposed_text="0.2 in",
            page=1,
            bbox=json.dumps({"x0": 0.0, "y0": 0.0, "x1": 400.0, "y1": 300.0}),
            span_index=0,
            status="open",
        )
        db.add(other)
        db.commit()
        other_id = other.id
    finally:
        db.close()

    resp = client.post(f"/api/v1/suggestions/{ids[0]}/apply-group")
    assert resp.status_code == 200, resp.text
    assert resp.json()["applied_count"] == 2

    untouched = client.get(f"/api/v1/suggestions/{other_id}").json()
    assert untouched["status"] == "open"


def test_apply_group_rejects_already_applied(client: TestClient) -> None:
    _, ids = _seed_group(pages=2)
    client.post(f"/api/v1/suggestions/{ids[0]}/apply-group")
    again = client.post(f"/api/v1/suggestions/{ids[0]}/apply-group")
    assert again.status_code == 409
    assert again.json()["code"] == "SUGGESTION_ALREADY_APPLIED"
