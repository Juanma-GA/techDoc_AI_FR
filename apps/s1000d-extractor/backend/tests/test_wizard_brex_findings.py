from __future__ import annotations

from app.core.wizard_response import project_dm_state


def test_generate_projection_separates_xml_brex_from_client_rule_findings() -> None:
    profile_violation = {
        "severity": "error",
        "rule": "BREX",
        "message": "Required object is absent.",
        "path": "//required-object",
        "brex_rule_id": "required-object",
    }
    client_rule_violation = {
        "severity": "error",
        "rule": "BREX_TITLE_LENGTH",
        "message": "Title is too long.",
        "path": "/",
    }
    dm = {
        "dm_id": "dm-1",
        "title": "Test DM",
        "dm_type": "descriptive",
        "tree": {"children": []},
        "xml": "<dmodule/>",
        "violations": [profile_violation, client_rule_violation],
    }

    state = project_dm_state(dm, "generate")

    assert state["brex_violations"] == [profile_violation]
    assert state["violation_count"] == 2


def test_completed_wizard_state_exposes_selected_profile_brex_findings(
    client, brex_xml: str, pdf_bytes: bytes
) -> None:
    brex_with_required_object = brex_xml.replace(
        "<structureObjectRule>",
        '<structureObjectRule id="must-exist">',
        1,
    ).replace(
        '<objectPath allowedObjectFlag="0">//emphasis</objectPath>',
        '<objectPath allowedObjectFlag="1">//brex-required-object</objectPath>',
        1,
    )
    profile_response = client.post(
        "/api/v1/brex",
        files={"file": ("project.brex", brex_with_required_object.encode("utf-8"))},
        data={"name": "Project rules", "s1000d_issue": "4.2"},
    )
    assert profile_response.status_code == 201, profile_response.text

    document_response = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", pdf_bytes)},
        data={
            "s1000d_issue": "4.2",
            "context_hint": "mixed",
            "brex_id": profile_response.json()["id"],
        },
    )
    assert document_response.status_code == 201, document_response.text
    document_id = document_response.json()["id"]

    client.post(f"/api/v1/documents/{document_id}/wizard/start", json={"cut_pdf": False})
    client.post(f"/api/v1/documents/{document_id}/wizard/advance", json={})
    client.post(
        f"/api/v1/documents/{document_id}/wizard/advance",
        json={"types": {}},
    )
    client.post(
        f"/api/v1/documents/{document_id}/wizard/advance",
        json={"overrides": []},
    )
    completed = client.post(
        f"/api/v1/documents/{document_id}/wizard/advance",
        json={},
    ).json()

    assert completed["step"] == "generate"
    assert completed["has_brex_profile"] is True
    violations = [
        violation
        for dm in completed["dms"]
        for violation in dm["brex_violations"]
    ]
    assert violations
    assert violations[0]["rule"] == "BREX"
    assert violations[0]["brex_rule_id"] == "must-exist"
