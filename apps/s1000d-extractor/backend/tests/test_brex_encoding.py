"""BREX uploads honor the XML encoding declaration and are normalized to UTF-8."""

from __future__ import annotations


def test_upload_accepts_declared_non_utf8_encoding_and_stores_utf8(client) -> None:
    xml = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>'
        '<dmodule><identAndStatusSection><dmAddress><dmIdent><dmCode '
        'modelIdentCode="TST" systemDiffCode="A" systemCode="A" subSystemCode="0" '
        'subSubSystemCode="0" assyCode="00" disassyCode="00" '
        'disassyCodeVariant="A" infoCode="040" infoCodeVariant="A" '
        'itemLocationCode="A"/></dmIdent></dmAddress></identAndStatusSection>'
        "<content><brex><contextRules><structureObjectRuleGroup>"
        '<structureObjectRule><objectPath allowedObjectFlag="0">//emphasis</objectPath>'
        "<objectUse>Emphasis&ndash;interdit par le projet.</objectUse>"
        "</structureObjectRule></structureObjectRuleGroup></contextRules></brex></content>"
        "</dmodule>"
    )
    uploaded = client.post(
        "/api/v1/brex",
        files={"file": ("profile.brex", xml.encode("iso-8859-1"))},
        data={"name": "Issue profile", "s1000d_issue": "4.2"},
    )

    assert uploaded.status_code == 201, uploaded.text
    detail = client.get(f"/api/v1/brex/{uploaded.json()['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["rules"][0]["object_use"] == "Emphasis\u2013interdit par le projet."


def test_upload_reports_unknown_named_entities(client) -> None:
    response = client.post(
        "/api/v1/brex",
        files={"file": ("unknown-entity.brex", b"<dmodule>&projectSpecificEntity;</dmodule>")},
        data={"name": "Unknown entity", "s1000d_issue": "4.2"},
    )

    assert response.status_code == 422
    assert "projectSpecificEntity" in response.json()["message"]


def test_issue_detection_uses_the_brex_schema_uri(client, brex_xml) -> None:
    xml = brex_xml.replace(
        "<dmodule>",
        '<dmodule xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="urn:descriptive '
        'http://www.s1000d.org/S1000D_4-0/xml_schema_flat/descript.xsd '
        'urn:brex http://www.s1000d.org/S1000D_4-1/xml_schema_flat/brex.xsd">',
    )
    uploaded = client.post(
        "/api/v1/brex",
        files={"file": ("profile.brex", xml.encode("utf-8"))},
        data={"name": "Issue detection", "s1000d_issue": "4.2"},
    )

    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["s1000d_issue"] == "4.1"
