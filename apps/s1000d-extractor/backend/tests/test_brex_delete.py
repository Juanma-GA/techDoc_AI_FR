"""Tests for deleting user BREX profiles."""

from pathlib import Path

from app.db.models import BrexProfile, Document
from app.db.session import SessionLocal


def _upload_brex(client, brex_xml: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/brex",
        files={"file": ("project.brex", brex_xml.encode("utf-8"))},
        data={"name": "Projet A", "s1000d_issue": "4.2"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_brex_delete_requires_confirmation_and_removes_xml(client, brex_xml) -> None:
    profile = _upload_brex(client, brex_xml)
    with SessionLocal() as db:
        xml_path = Path(db.get(BrexProfile, profile["id"]).xml_path)

    unconfirmed = client.delete(f"/api/v1/brex/{profile['id']}")
    assert unconfirmed.status_code == 422
    assert unconfirmed.json()["code"] == "DELETE_NOT_CONFIRMED"
    assert xml_path.is_file()

    deleted = client.delete(
        f"/api/v1/brex/{profile['id']}?confirm_token=test-confirm-token"
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"id": profile["id"], "status": "deleted"}
    assert client.get("/api/v1/brex").json() == []
    assert not xml_path.exists()


def test_brex_delete_is_blocked_while_a_document_uses_it(
    client, brex_xml, pdf_bytes
) -> None:
    profile = _upload_brex(client, brex_xml)
    document = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", pdf_bytes)},
        data={
            "s1000d_issue": "4.2",
            "context_hint": "mixed",
            "brex_id": profile["id"],
        },
    )
    assert document.status_code == 201, document.text

    response = client.delete(
        f"/api/v1/brex/{profile['id']}?confirm_token=test-confirm-token"
    )
    assert response.status_code == 409
    assert response.json()["code"] == "BREX_IN_USE"
    assert client.get(f"/api/v1/brex/{profile['id']}").status_code == 200
    with SessionLocal() as db:
        stored_document = db.get(Document, document.json()["id"])
        assert stored_document is not None
        assert stored_document.brex_id == profile["id"]
