from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.admin import _remove_storage_dir
from app.core.feedback import load_exclusions
from app.db.models import AppConfig, Document, Suggestion
from app.db.session import SessionLocal


@pytest.fixture(autouse=True)
def clean_demo_scope_test_data():
    with SessionLocal() as db:
        baseline_ids = set(db.scalars(select(Document.id)))
        db.execute(
            delete(AppConfig).where(
                AppConfig.key.in_(
                    (
                        "demo_enabled",
                        "document.context_defaults",
                        "document.context_defaults.demo",
                    )
                )
            )
        )
        db.commit()
    yield
    with SessionLocal() as db:
        created = list(
            db.scalars(select(Document).where(Document.id.notin_(baseline_ids)))
        )
        storage_dirs = [doc.storage_dir for doc in created]
        for doc in created:
            db.delete(doc)
        db.execute(
            delete(AppConfig).where(
                AppConfig.key.in_(
                    (
                        "demo_enabled",
                        "document.context_defaults",
                        "document.context_defaults.demo",
                    )
                )
            )
        )
        db.commit()
    for storage_dir in storage_dirs:
        _remove_storage_dir(storage_dir)


def _upload(client: TestClient, filename: str, pdf: bytes) -> dict:
    response = client.post(
        "/api/v1/documents",
        files={"file": (filename, pdf, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_document_and_suggestion_lists_are_isolated_by_mode(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    normal_before = {
        doc["id"] for doc in client.get("/api/v1/documents").json()
    }
    normal_doc = _upload(client, "normal.pdf", sample_pdf_bytes)
    demo_enabled = client.post(
        "/api/v1/settings/mistral",
        json={"demo_enabled": True},
    )
    assert demo_enabled.status_code == 200
    demo_before = {
        doc["id"] for doc in client.get("/api/v1/documents").json()
    }
    demo_doc = _upload(client, "demo.pdf", sample_pdf_bytes)
    with SessionLocal() as db:
        normal_row = db.get(Document, UUID(normal_doc["id"]))
        demo_row = db.get(Document, UUID(demo_doc["id"]))
    assert normal_row is not None and normal_row.is_demo is False
    assert demo_row is not None and demo_row.is_demo is True
    assert normal_row.storage_dir.startswith("document_")
    assert demo_row.storage_dir.startswith("demo_document_")

    with SessionLocal() as db:
        db.add_all(
            [
                Suggestion(
                    document_id=UUID(normal_doc["id"]),
                    rule_kind="content",
                    rule_code="NORMAL_TEST_RULE",
                    message="normal-only",
                    status="rejected",
                    feedback="normal feedback",
                ),
                Suggestion(
                    document_id=UUID(demo_doc["id"]),
                    rule_kind="content",
                    rule_code="DEMO_TEST_RULE",
                    message="demo-only",
                    status="rejected",
                    feedback="demo feedback",
                ),
                Suggestion(
                    document_id=UUID(normal_doc["id"]),
                    rule_kind="content",
                    rule_code="AI_SCAN",
                    message="normal AI finding",
                    original_text="normal-only AI text",
                    status="rejected",
                ),
                Suggestion(
                    document_id=UUID(demo_doc["id"]),
                    rule_kind="content",
                    rule_code="AI_SCAN",
                    message="demo AI finding",
                    original_text="demo-only AI text",
                    status="rejected",
                ),
            ]
        )
        db.commit()

    demo_documents = client.get("/api/v1/documents").json()
    demo_suggestions = client.get("/api/v1/suggestions").json()
    demo_document_ids = {doc["id"] for doc in demo_documents}
    demo_rule_codes = {item["rule_code"] for item in demo_suggestions}
    assert demo_document_ids == demo_before | {demo_doc["id"]}
    assert "DEMO_TEST_RULE" in demo_rule_codes
    assert "NORMAL_TEST_RULE" not in demo_rule_codes
    with SessionLocal() as db:
        demo_exclusions = load_exclusions(db)
    assert ("AI_SCAN", "demo-only AI text") in demo_exclusions
    assert ("AI_SCAN", "normal-only AI text") not in demo_exclusions
    assert client.get(f"/api/v1/documents/{normal_doc['id']}").status_code == 404
    assert client.get(
        f"/api/v1/documents/{normal_doc['id']}/rule-results"
    ).status_code == 404
    assert client.get(f"/api/v1/documents/{demo_doc['id']}").status_code == 200
    demo_rejections = client.get(
        "/api/v1/suggestions/rejections-summary?synthesize=false"
    ).json()
    demo_rejection_codes = {item["rule_code"] for item in demo_rejections["items"]}
    assert "DEMO_TEST_RULE" in demo_rejection_codes
    assert "NORMAL_TEST_RULE" not in demo_rejection_codes

    normal_enabled = client.post(
        "/api/v1/settings/mistral",
        json={"demo_enabled": False},
    )
    assert normal_enabled.status_code == 200
    normal_documents = client.get("/api/v1/documents").json()
    normal_suggestions = client.get("/api/v1/suggestions").json()
    assert {doc["id"] for doc in normal_documents} == normal_before | {
        normal_doc["id"]
    }
    normal_rule_codes = {item["rule_code"] for item in normal_suggestions}
    assert "NORMAL_TEST_RULE" in normal_rule_codes
    assert "DEMO_TEST_RULE" not in normal_rule_codes
    with SessionLocal() as db:
        normal_exclusions = load_exclusions(db)
    assert ("AI_SCAN", "normal-only AI text") in normal_exclusions
    assert ("AI_SCAN", "demo-only AI text") not in normal_exclusions
    assert client.get(f"/api/v1/documents/{demo_doc['id']}").status_code == 404
    normal_rejections = client.get(
        "/api/v1/suggestions/rejections-summary?synthesize=false"
    ).json()
    normal_rejection_codes = {
        item["rule_code"] for item in normal_rejections["items"]
    }
    assert "NORMAL_TEST_RULE" in normal_rejection_codes
    assert "DEMO_TEST_RULE" not in normal_rejection_codes


def test_demo_context_defaults_are_separate_and_manufacturer_is_not_mapped(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    normal = _upload(client, "normal-context.pdf", sample_pdf_bytes)
    normal_context = {
        "meta_revision_date": "DEC 2024",
        "meta_cmm_number": "79-30-02",
        "meta_first_issue_date": "JAN 2000",
        "meta_revision_number": "04",
        "meta_pnr_number": "1-111-AA",
        "document_language": "fr",
    }
    saved_normal_context = client.patch(
        f"/api/v1/documents/{normal['id']}",
        json=normal_context,
    )
    assert saved_normal_context.status_code == 200, saved_normal_context.text

    client.post("/api/v1/settings/mistral", json={"demo_enabled": True})
    demo_config = client.get("/api/v1/client-config").json()
    assert "meta_manufacturer" not in demo_config["mapping"]["fields"]
    demo = _upload(client, "demo-context.pdf", sample_pdf_bytes)

    assert demo["client_metadata"]["meta_revision_date"] == "JUL 27/26"
    assert demo["client_metadata"]["meta_cmm_number"] == "80-80-01"
    assert demo["client_metadata"]["meta_first_issue_date"] == "JUL 25/95"
    assert demo["client_metadata"]["meta_revision_number"] == "01"
    assert demo["client_metadata"]["meta_pnr_number"] == ["1-900-SB"]
    assert demo["client_metadata"]["document_language"] == "en"
    assert "meta_manufacturer" not in demo["client_metadata"]

    client.post("/api/v1/settings/mistral", json={"demo_enabled": False})
    normal_after_demo = _upload(client, "normal-after-demo.pdf", sample_pdf_bytes)
    assert normal_after_demo["client_metadata"]["meta_revision_date"] == "DEC 2024"
    assert normal_after_demo["client_metadata"]["meta_pnr_number"] == ["1-111-AA"]


def test_demo_reset_does_not_delete_normal_documents(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    normal = _upload(client, "normal-preserved.pdf", sample_pdf_bytes)
    client.post("/api/v1/settings/mistral", json={"demo_enabled": True})
    demo_before = client.get("/api/v1/documents").json()
    demo = _upload(client, "demo-reset.pdf", sample_pdf_bytes)

    reset = client.post("/api/v1/admin/reset")

    assert reset.status_code == 200, reset.text
    assert reset.json()["documents_deleted"] == len(demo_before) + 1
    assert reset.json()["rules_deleted"] == 0
    assert [doc["id"] for doc in client.get("/api/v1/documents").json()] == []
    client.post("/api/v1/settings/mistral", json={"demo_enabled": False})
    normal_ids = {doc["id"] for doc in client.get("/api/v1/documents").json()}
    assert normal["id"] in normal_ids
    assert client.get(f"/api/v1/documents/{demo['id']}").status_code == 404
