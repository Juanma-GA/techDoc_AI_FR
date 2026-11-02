def test_manual_dmrl_links_validate_each_link_with_pydantic(client) -> None:
    invalid = client.post(
        "/api/v1/documents/unknown/link-dmrl",
        json={"mode": "manual", "dmrl_links": [{"dm_code": "DMC-SYNTHETIC", "extra": "value"}]},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "VALIDATION_ERROR"

    valid_shape = client.post(
        "/api/v1/documents/unknown/link-dmrl",
        json={"mode": "manual", "dmrl_links": [{"dmrl_line_id": "line-1", "dm_code": "DMC-SYNTHETIC"}]},
    )
    assert valid_shape.status_code == 404
    assert valid_shape.json()["code"] == "DOC_NOT_FOUND"


def test_manual_dmrl_links_create_links_from_typed_entries(client, pdf_bytes) -> None:
    uploaded = client.post(
        "/api/v1/documents",
        files={"file": ("synthetic.pdf", pdf_bytes, "application/pdf")},
        data={"s1000d_issue": "4.2", "context_hint": "mixed"},
    )
    assert uploaded.status_code == 201, uploaded.text
    doc_id = uploaded.json()["id"]
    resource = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={
            "file": (
                "dmrl.json",
                b'[{"Arbo":"1","DMC":"DMC-SYNTHETIC","Titre":"Synthetic"}]',
                "application/json",
            ),
        },
    )
    assert resource.status_code == 200, resource.text

    response = client.post(
        f"/api/v1/documents/{doc_id}/link-dmrl",
        json={
            "mode": "manual",
            "dmrl_links": [{"dmrl_line_id": "line-1", "dm_code": "DMC-SYNTHETIC"}],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["links_created"] == 1
    links = client.get(f"/api/v1/documents/{doc_id}/dm-links")
    assert links.status_code == 200
    assert links.json()[0]["dmrl_line_id"] == "line-1"
    assert links.json()[0]["dm_code"] == "DMC-SYNTHETIC"
