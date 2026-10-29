"""Wizard navigation regression tests."""


def test_back_from_generation_returns_to_editable_structure_step(client, pdf_bytes) -> None:
    uploaded = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", pdf_bytes)},
        data={"s1000d_issue": "4.2", "context_hint": "mixed"},
    )
    assert uploaded.status_code == 201, uploaded.text
    doc_id = uploaded.json()["id"]
    detection = client.post(
        f"/api/v1/documents/{doc_id}/pdf-cut/detect"
    ).json()
    if detection["validation_required"]:
        confirmed = client.post(
            f"/api/v1/documents/{doc_id}/pdf-cut/confirm",
            json={
                "start_page": detection["selected_page"] or detection["default_start_page"],
                "end_page": detection["selected_end_page"] or detection["total_pages"],
            },
        )
        assert confirmed.status_code == 200, confirmed.text

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert state["step"] == "split"
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["step"] == "type"
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance",
        json={"types": {}},
    ).json()
    assert state["step"] == "structure"
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance",
        json={"overrides": []},
    ).json()
    assert state["step"] == "generate"

    returned = client.post(f"/api/v1/documents/{doc_id}/wizard/back")

    assert returned.status_code == 200
    assert returned.json()["step"] == "structure"
    assert client.get(f"/api/v1/documents/{doc_id}").json()["status"] == "wizard"
