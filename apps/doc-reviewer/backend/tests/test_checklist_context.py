"""Checklist reference context settings used before Excel import."""

from fastapi.testclient import TestClient


def test_checklist_context_round_trip(client: TestClient) -> None:
    initial = client.get("/api/v1/settings/checklist-context")
    assert initial.status_code == 200
    assert initial.json() == {
        "meta_revision_date": None,
        "meta_cmm_number": None,
        "meta_first_issue_date": None,
        "meta_revision_number": None,
        "document_language": None,
    }

    updated = client.post(
        "/api/v1/settings/checklist-context",
        json={
            "meta_revision_date": " MAR 18/26 ",
            "meta_cmm_number": "32-11-00",
            "document_language": "en",
        },
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "meta_revision_date": "MAR 18/26",
        "meta_cmm_number": "32-11-00",
        "meta_first_issue_date": None,
        "meta_revision_number": None,
        "document_language": "en",
    }

    cleared = client.post(
        "/api/v1/settings/checklist-context",
        json={"meta_revision_date": None, "document_language": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["meta_revision_date"] is None
    assert cleared.json()["document_language"] is None
