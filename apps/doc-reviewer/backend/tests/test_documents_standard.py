"""Coverage for the `standard_version_id` query param on /documents."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _get_version_id(client: TestClient, code: str) -> str:
    body = client.get("/api/v1/standards").json()
    std = next(s for s in body if s["code"] == code)
    return std["versions"][0]["id"]


def test_upload_with_standard_version_id_persists_it(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    sv = _get_version_id(client, "MAT10000")
    resp = client.post(
        f"/api/v1/documents?target=auto&standard_version_id={sv}",
        files={"file": ("a.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["standard_version_id"] == sv


def test_upload_without_standard_version_id_uses_active_bundle_versions(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    active_version = _get_version_id(client, "THALES-CUSTOM")
    resp = client.post(
        "/api/v1/documents?target=auto",
        files={"file": ("b.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201
    assert resp.json()["standard_version_id"] == active_version
    assert resp.json()["standard_version_ids"] == [active_version]


def test_upload_with_unknown_standard_version_id_400(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    import uuid

    resp = client.post(
        f"/api/v1/documents?target=auto&standard_version_id={uuid.uuid4()}",
        files={"file": ("c.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "STANDARD_VERSION_NOT_FOUND"
