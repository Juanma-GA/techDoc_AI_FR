"""Admin reset endpoints — full wipe + storage cleanup."""

from __future__ import annotations

import uuid
from pathlib import Path

import fitz
from fastapi.testclient import TestClient


def _upload(client: TestClient, sample_pdf_bytes: bytes, name: str = "x.pdf") -> str:
    resp = client.post(
        "/api/v1/documents",
        files={"file": (name, sample_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_wipe_suggestions_clears_every_status(client: TestClient, sample_pdf_bytes: bytes) -> None:
    """`POST /admin/wipe-suggestions` deletes open, rejected, applied,
    edited — every status. The historic « clear open » button only
    touched status=open which left rejected/applied cluttering the UI."""
    doc_id = _upload(client, sample_pdf_bytes)

    # Manually insert suggestions in every status by going through the DB
    # (faster than triggering a real analyse pipeline).
    from app.db.models import Suggestion
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        for status in ("open", "rejected", "edited", "applied"):
            db.add(
                Suggestion(
                    id=uuid.uuid4(),
                    document_id=uuid.UUID(doc_id),
                    rule_kind="custom",
                    rule_code="TEST",
                    severity="warning",
                    message="m",
                    original_text="x",
                    proposed_text="y",
                    page=1,
                    status=status,
                )
            )
        db.commit()
    finally:
        db.close()

    list_resp = client.get(f"/api/v1/documents/{doc_id}/suggestions")
    assert len(list_resp.json()) == 4

    reset_resp = client.post("/api/v1/admin/wipe-suggestions")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["deleted"] == 4

    after = client.get(f"/api/v1/documents/{doc_id}/suggestions")
    assert after.json() == []


def _storage_dir_for(doc_id: str) -> str:
    """Mirror the naming convention used by `_create_document`."""
    import uuid as _uuid
    return f"document_{_uuid.UUID(doc_id).hex}"


def test_reset_all_deletes_docs_and_storage(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    """`POST /admin/reset` drops every Document AND cleans the
    `data/storage/document_*/` folder on disk."""
    from app.config import settings as _settings
    from app.core.compiled_rule_store import persist_compiled_rule
    from app.core.compiled_rules import CompiledRule, RuleTarget
    from app.db.models import Rule
    from app.db.session import SessionLocal

    storage_root = Path(_settings.storage_dir)
    doc_a = _upload(client, sample_pdf_bytes, name="alpha.pdf")
    doc_b = _upload(client, sample_pdf_bytes, name="beta.pdf")

    target_a = storage_root / _storage_dir_for(doc_a)
    target_b = storage_root / _storage_dir_for(doc_b)
    assert target_a.is_dir() and target_b.is_dir()

    # Drop an orphan folder that shouldn't survive the sweep.
    orphan = storage_root / "document_orphan_xyz_test"
    orphan.mkdir(exist_ok=True)
    (orphan / "v0.pdf").write_bytes(b"%PDF-1.4\n")

    db = SessionLocal()
    try:
        db.add(
            Rule(
                name="Synthetic reset rule",
                kind="regex_flag",
                pattern="reset",
                replacement="",
                severity="warning",
                message="Synthetic",
                enabled=True,
            )
        )
        persist_compiled_rule(
            db,
            CompiledRule(
                id="synthetic-reset-checklist",
                topic="Synthetic checklist",
                execution="unsupported",
                target=RuleTarget(page="all", region="full_page"),
                compilation_error="Synthetic",
                source="user_checklist",
            ),
        )
        db.commit()
    finally:
        db.close()

    reset = client.post("/api/v1/admin/reset")
    assert reset.status_code == 200
    body = reset.json()
    assert body["documents_deleted"] >= 2
    assert body["rules_deleted"] >= 1
    assert body["checklist_rules_deleted"] >= 1
    assert body["orphan_folders_cleaned"] >= 1

    # DB is empty.
    assert client.get("/api/v1/documents").json() == []
    assert client.get("/api/v1/rules").json() == []
    assert client.get("/api/v1/compiled-rules").json() == []
    # Disk is clean for the doc we just uploaded.
    assert not target_a.exists()
    assert not target_b.exists()
    assert not orphan.exists()


def test_delete_document_removes_storage_and_preparation_session(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    """Single-doc DELETE removes preparation state and its storage folder."""
    from sqlalchemy import select

    from app.config import settings as _settings
    from app.db.preparation_models import DocumentPreparation
    from app.db.session import SessionLocal

    doc_id = _upload(client, sample_pdf_bytes)
    target = Path(_settings.storage_dir) / _storage_dir_for(doc_id)
    assert target.is_dir()
    preparation = client.get(f"/api/v1/documents/{doc_id}/preparation")
    assert preparation.status_code == 200, preparation.text

    db = SessionLocal()
    try:
        assert db.scalar(
            select(DocumentPreparation).where(
                DocumentPreparation.document_id == uuid.UUID(doc_id)
            )
        ) is not None
    finally:
        db.close()

    delete_resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert delete_resp.status_code == 204
    assert not target.exists()

    db = SessionLocal()
    try:
        assert db.scalar(
            select(DocumentPreparation).where(
                DocumentPreparation.document_id == uuid.UUID(doc_id)
            )
        ) is None
    finally:
        db.close()
