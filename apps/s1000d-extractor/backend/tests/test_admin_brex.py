"""Admin (stats/reset) + upload BREX."""

from __future__ import annotations

from lxml import etree


def test_brex_upload_and_list(client, brex_xml) -> None:
    r = client.post(
        "/api/v1/brex",
        files={"file": ("project.brex", brex_xml.encode("utf-8"))},
        data={"name": "Projet A", "s1000d_issue": "5.0"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Projet A"
    listing = client.get("/api/v1/brex").json()
    assert len(listing) == 1


def test_brex_upload_accepts_empty_internal_doctype(client, brex_xml) -> None:
    xml = brex_xml.replace(
        '<?xml version="1.0"?>',
        '<?xml version="1.0"?>\n<!DOCTYPE dmodule [\n]>',
    )
    response = client.post(
        "/api/v1/brex",
        files={"file": ("project.brex", xml.encode("utf-8"))},
        data={"name": "Projet A", "s1000d_issue": "4.2"},
    )
    assert response.status_code == 201, response.text


def test_brex_upload_rejects_external_doctype(client, brex_xml) -> None:
    xml = brex_xml.replace(
        '<?xml version="1.0"?>',
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE dmodule SYSTEM "file:///not-loaded.dtd">',
    )
    response = client.post(
        "/api/v1/brex",
        files={"file": ("external.brex", xml.encode("utf-8"))},
        data={"name": "External", "s1000d_issue": "4.2"},
    )
    assert response.status_code == 422
    assert "DTD externe interdite" in response.json()["message"]


def test_brex_issue_is_read_from_its_schema_location(client, brex_xml) -> None:
    xml = brex_xml.replace(
        "<dmodule>",
        '<dmodule xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:noNamespaceSchemaLocation="http://www.s1000d.org/'
        'S1000D_4-1/xml_schema_flat/brex.xsd">',
    )
    response = client.post(
        "/api/v1/brex",
        files={"file": ("issue-4.1.brex", xml.encode("utf-8"))},
        data={"name": "Issue 4.1", "s1000d_issue": "4.2"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["s1000d_issue"] == "4.1"


def test_brex_detail_exposes_dmc_and_parsed_rules(client, brex_xml) -> None:
    commented_xml = brex_xml.replace("<dmodule>", "<dmodule><!-- BREX comment -->")
    uploaded = client.post(
        "/api/v1/brex",
        files={"file": ("project.brex", commented_xml.encode("utf-8"))},
        data={"name": "Projet A", "s1000d_issue": "4.2"},
    )
    detail = client.get(f"/api/v1/brex/{uploaded.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["dm_code"]["modelIdentCode"] == "TST"
    assert detail.json()["rules"][0]["allowed_flag"] == "0"
    assert detail.json()["rules"][0]["object_path"] == "//emphasis"


def test_valid_brex_without_structure_rules_is_stored_and_reported(client) -> None:
    xml = (
        "<dmodule><identAndStatusSection><dmAddress><dmIdent><dmCode "
        'modelIdentCode="TST" systemDiffCode="A" systemCode="A" subSystemCode="0" '
        'subSubSystemCode="0" assyCode="00" disassyCode="00" '
        'disassyCodeVariant="A" infoCode="040" infoCodeVariant="A" '
        'itemLocationCode="A"/></dmIdent></dmAddress></identAndStatusSection>'
        "<content><brex><nonContextRules><nonContextRule>"
        "<simplePara>Review this requirement manually.</simplePara>"
        "</nonContextRule></nonContextRules></brex></content></dmodule>"
    )
    uploaded = client.post(
        "/api/v1/brex",
        files={"file": ("narrative.brex", xml.encode("utf-8"))},
        data={"name": "Narrative", "s1000d_issue": "4.2"},
    )
    assert uploaded.status_code == 201, uploaded.text
    detail = client.get(f"/api/v1/brex/{uploaded.json()['id']}").json()
    assert detail["rules"] == []
    assert detail["unsupported_rules"][0]["rule_type"] == "nonContextRule"


def test_bad_brex_rejected(client) -> None:
    r = client.post(
        "/api/v1/brex",
        files={"file": ("x.xml", b"<root>pas un brex</root>")},
        data={"name": "X", "s1000d_issue": "5.0"},
    )
    assert r.status_code == 422


def test_document_upload_blocks_brex_issue_mismatch(client, brex_xml, pdf_bytes) -> None:
    brex = client.post(
        "/api/v1/brex",
        files={"file": ("project.brex", brex_xml.encode("utf-8"))},
        data={"name": "Projet A", "s1000d_issue": "4.1"},
    ).json()
    response = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", pdf_bytes)},
        data={
            "s1000d_issue": "4.2",
            "context_hint": "mixed",
            "brex_id": brex["id"],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "BREX_ISSUE_MISMATCH"


def test_generated_dm_references_selected_brex_dmc(client, brex_xml, pdf_bytes) -> None:
    brex = client.post(
        "/api/v1/brex",
        files={"file": ("project.brex", brex_xml.encode("utf-8"))},
        data={"name": "Projet A", "s1000d_issue": "4.2"},
    ).json()
    uploaded = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", pdf_bytes)},
        data={
            "s1000d_issue": "4.2",
            "context_hint": "mixed",
            "brex_id": brex["id"],
        },
    )
    assert uploaded.status_code == 201, uploaded.text
    doc_id = uploaded.json()["id"]
    client.post(f"/api/v1/documents/{doc_id}/wizard/start", json={"cut_pdf": False})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"types": {}})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"overrides": []})
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    dm_id = state["dms"][0]["dm_id"]

    response = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{dm_id}/xml")
    assert response.status_code == 200, response.text
    root = etree.fromstring(response.content)
    dm_code = root.find(
        "./identAndStatusSection/dmStatus/brexDmRef/dmRef/dmRefIdent/dmCode"
    )
    assert dm_code is not None
    assert dm_code.get("modelIdentCode") == "TST"
    assert dm_code.get("infoCode") == "040"


def test_stats_and_reset_preserve_brex(client, pdf_bytes, brex_xml) -> None:
    client.post(
        "/api/v1/brex",
        files={"file": ("p.brex", brex_xml.encode("utf-8"))},
        data={"name": "P", "s1000d_issue": "5.0"},
    )
    client.post(
        "/api/v1/documents",
        files={"file": ("m.pdf", pdf_bytes)},
        data={"s1000d_issue": "4.2", "context_hint": "mixed"},
    )
    stats = client.get("/api/v1/admin/stats").json()
    assert stats["documents"] == 1 and stats["brex_profiles"] == 1

    r = client.post(
        "/api/v1/admin/reset/documents?confirm_token=test-reset-token",
    )
    assert r.status_code == 200
    after = client.get("/api/v1/admin/stats").json()
    assert after["documents"] == 0
    assert after["brex_profiles"] == 1  # BREX preserve
