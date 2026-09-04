"""POST /documents/{id}/dm-versions/{dm_code} — H-NEW-08 remediation.

The DM XML content used to be accepted as a query parameter (unvalidated,
unbounded, ending up in the URL/access logs). It is now a validated Pydantic
body with an explicit size limit, matching every other upload endpoint.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def doc_id() -> str:
    from app.db.models import Document
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        doc = Document(
            filename="manual.pdf",
            source_format="pdf",
            storage_path="/tmp/manual.pdf",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc.id
    finally:
        db.close()


def test_save_dm_version_accepts_json_body(client, doc_id) -> None:
    res = client.post(
        f"/api/v1/documents/{doc_id}/dm-versions/DMC-BRAKE-A-00",
        json={"content": "<dmodule/>", "author": "jdoe", "status": "draft", "notes": "first cut"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["dm_code"] == "DMC-BRAKE-A-00"
    assert body["author"] == "jdoe"
    assert body["content_length"] == len("<dmodule/>")


def test_save_dm_version_rejects_missing_content(client, doc_id) -> None:
    res = client.post(
        f"/api/v1/documents/{doc_id}/dm-versions/DMC-BRAKE-A-00",
        json={"author": "jdoe"},
    )
    assert res.status_code == 422


def test_save_dm_version_content_not_accepted_as_query_param(client, doc_id) -> None:
    """The old query-param form must no longer work (content is body-only now)."""
    res = client.post(
        f"/api/v1/documents/{doc_id}/dm-versions/DMC-BRAKE-A-00?content=%3Cdmodule/%3E",
    )
    assert res.status_code == 422


def test_save_dm_version_rejects_oversized_content(client, doc_id, monkeypatch) -> None:
    from app.api import dm_versions

    monkeypatch.setattr(dm_versions.settings, "max_upload_size_mb", 0)  # -> 0 bytes allowed
    res = client.post(
        f"/api/v1/documents/{doc_id}/dm-versions/DMC-BRAKE-A-00",
        json={"content": "<dmodule/>"},
    )
    assert res.status_code == 413


def test_save_dm_version_unknown_doc_404(client) -> None:
    res = client.post(
        "/api/v1/documents/does-not-exist/dm-versions/DMC-BRAKE-A-00",
        json={"content": "<dmodule/>"},
    )
    assert res.status_code == 404
