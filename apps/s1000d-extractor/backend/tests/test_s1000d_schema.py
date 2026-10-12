"""Validation des sorties contre les schemas S1000D disponibles."""

from __future__ import annotations

from app.core import s1000d_schema
from app.core.ir import IRNode
from app.core.resolver import resolve
from app.core.s1000d_serializer import missing_data_fields, serialize
from app.core.validator import validate_document


def _root() -> IRNode:
    return IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="s", kind="section", level=1, text="1 Test", children=[
            IRNode(id="p", kind="paragraph", text="Contenu."),
        ]),
    ])


def test_issue_4_1_schema_is_discovered_from_repository() -> None:
    assert s1000d_schema.is_installed("4.1") is True
    assert s1000d_schema._find_dm_xsd("4.1", "descriptive").name == "descript.xsd"
    assert s1000d_schema._find_dm_xsd("4.1", "procedural").name == "proced.xsd"
    assert s1000d_schema._find_dm_xsd("4.2", "ipd").name == "ipd.xsd"


def test_unknown_dm_type_does_not_fall_back_to_another_schema() -> None:
    root = _root()
    resolve(root)
    xml = serialize(root, issue="4.2", dm_type="descriptive")

    violations = s1000d_schema.validate_xsd(
        xml, "4.2", dm_type="unknown", allow_internal_dtd=True,
    )

    assert len(violations) == 1
    assert violations[0]["severity"] == "info"
    assert "Aucun schema DM correspondant" in violations[0]["message"]


def test_missing_dmc_values_are_schema_compatible_and_reported() -> None:
    root = _root()
    resolve(root)

    for issue in ("4.1", "4.2"):
        xml = serialize(root, issue=issue, dm_type="descriptive")
        violations = s1000d_schema.validate_xsd(
            xml, issue, dm_type="descriptive", allow_internal_dtd=True,
        )

        assert not [v for v in violations if v["severity"] == "error"], violations
        assert "TODO" not in xml
        missing = missing_data_fields(xml)
        assert any("dmCode/@modelIdentCode" in field for field in missing)
        assert any("dmCode/@infoCode" in field for field in missing)


def test_default_header_does_not_trigger_missing_data_warning() -> None:
    root = _root()
    resolve(root)
    xml = serialize(
        root,
        issue="4.2",
        dm_type="descriptive",
        dm_metadata={"dmc": "DMC-WEG-A-00-00-00-00A-040A-D"},
    )

    assert missing_data_fields(xml) == []


def test_validator_runs_the_issue_4_1_descriptive_schema() -> None:
    root = _root()
    resolve(root)
    xml = serialize(
        root,
        issue="4.1",
        dm_type="descriptive",
        dm_metadata={"dmc": "DMC-WEG-A-00-00-00-00A-040A-D"},
    )

    violations = validate_document(xml, issue="4.1", dm_type="descriptive")

    assert not [violation for violation in violations if violation["rule"] == "XSD"]


def test_validator_runs_the_issue_4_1_procedural_schema() -> None:
    root = _root()
    root.children[0].context = "procedural"
    root.children[0].children[0].context = "procedural"
    resolve(root)
    xml = serialize(
        root,
        issue="4.1",
        dm_type="procedural",
        dm_metadata={"dmc": "DMC-WEG-A-00-00-00-00A-520A-D"},
    )

    violations = validate_document(xml, issue="4.1", dm_type="procedural")

    assert not [violation for violation in violations if violation["rule"] == "XSD"]
