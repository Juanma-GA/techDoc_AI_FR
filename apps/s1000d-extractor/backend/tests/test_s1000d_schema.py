"""Validation des sorties contre les schemas S1000D disponibles."""

from __future__ import annotations

from app.core import s1000d_schema
from app.core.ir import IRNode
from app.core.resolver import resolve
from app.core.s1000d_serializer import serialize
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


def test_validator_runs_the_issue_4_1_descriptive_schema() -> None:
    root = _root()
    resolve(root)
    xml = serialize(root, issue="4.1", dm_type="descriptive")

    violations = validate_document(xml, issue="4.1", dm_type="descriptive")

    assert not [violation for violation in violations if violation["rule"] == "XSD"]


def test_validator_runs_the_issue_4_1_procedural_schema() -> None:
    root = _root()
    root.children[0].context = "procedural"
    root.children[0].children[0].context = "procedural"
    resolve(root)
    xml = serialize(root, issue="4.1", dm_type="procedural")

    violations = validate_document(xml, issue="4.1", dm_type="procedural")

    assert not [violation for violation in violations if violation["rule"] == "XSD"]
