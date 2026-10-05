"""Validation de Data Modules importes sans BREX."""

from __future__ import annotations

from app.core.dm_validation import validate_dm
from app.core.ir import IRNode
from app.core.resolver import resolve
from app.core.s1000d_serializer import serialize


def _valid_dm(issue: str = "4.1", dm_type: str = "descriptive") -> str:
    paragraph = IRNode(id="paragraph", kind="paragraph", text="Contenu.")
    section = IRNode(id="section", kind="section", level=1, text="1 Test", children=[paragraph])
    if dm_type == "procedural":
        section.context = "procedural"
        paragraph.context = "procedural"
    root = IRNode(id="root", kind="section", level=0, children=[
        section,
    ])
    resolve(root)
    return serialize(root, issue=issue, dm_type=dm_type)


def test_detects_issue_and_schema_from_schema_location() -> None:
    result = validate_dm(_valid_dm("4.1").encode(), filename="test.xml")

    assert result["status"] == "valid"
    assert result["issue"] == "4.1"
    assert result["schema"] == "descript"
    assert result["error_count"] == 0


def test_detects_issue_42_procedural_schema() -> None:
    result = validate_dm(
        _valid_dm("4.2", "procedural").encode(),
        filename="procedural.xml",
    )

    assert result["status"] == "valid"
    assert result["issue"] == "4.2"
    assert result["schema"] == "proced"


def test_reports_xsd_location_for_invalid_element() -> None:
    xml = _valid_dm().replace("</content>", "<notAS1000DElement/></content>")

    result = validate_dm(xml.encode(), filename="invalid.xml")

    assert result["status"] == "invalid"
    error = next(v for v in result["violations"] if v["rule"] == "XSD")
    assert error["line"] > 0
    assert error["path"]
    assert error["message"]


def test_unknown_issue_waits_for_user_selection() -> None:
    xml = _valid_dm().replace(
        'xsi:noNamespaceSchemaLocation="http://www.s1000d.org/S1000D_4-1/xml_schema_flat/descript.xsd"',
        "",
    )

    result = validate_dm(xml.encode(), filename="unknown.xml")

    assert result["status"] == "needs_issue"
    assert result["issue"] is None


def test_issue_five_is_reported_as_unverifiable_without_schema() -> None:
    result = validate_dm(_valid_dm().encode(), filename="legacy.xml", issue_override="5.0")

    assert result["status"] == "unverifiable"
    assert result["issue"] == "5.0"
    assert result["error_count"] == 0


def test_validation_api_accepts_multiple_dms(client) -> None:
    valid = _valid_dm("4.1").encode()
    invalid = _valid_dm("4.2").replace("</content>", "<notAS1000DElement/></content>").encode()

    response = client.post(
        "/api/v1/validation/dms",
        files=[
            ("files", ("valid.xml", valid, "application/xml")),
            ("files", ("invalid.xml", invalid, "application/xml")),
        ],
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert [result["status"] for result in results] == ["valid", "invalid"]
    assert [result["issue"] for result in results] == ["4.1", "4.2"]


def test_validates_declared_legacy_encoding() -> None:
    xml = _valid_dm().replace("encoding='UTF-8'", "encoding='ISO-8859-1'").replace(
        "Contenu.", "Résumé."
    )

    result = validate_dm(xml.encode("iso-8859-1"), filename="legacy-encoding.xml")

    assert result["status"] == "valid"