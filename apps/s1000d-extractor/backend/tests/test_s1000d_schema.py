"""Validation des sorties contre les schemas S1000D disponibles."""

from __future__ import annotations

from copy import deepcopy

from app.core import xml_safe
from app.core import s1000d_schema
from app.core.ir import IRNode
from app.core.resolver import resolve
from app.core.s1000d_serializer import SerializationDiagnostics, missing_data_fields, serialize
from app.core.validator import validate_document
from app.core.xsd_model import load_xsd_model


def _root() -> IRNode:
    return IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="s", kind="section", level=1, text="1 Test", children=[
            IRNode(id="p", kind="paragraph", text="Contenu."),
        ]),
    ])


def test_issue_4_1_schema_is_discovered_from_repository() -> None:
    assert s1000d_schema.is_installed("4.1") is True
    descriptive_schema = s1000d_schema._find_dm_xsd("4.1", "descriptive")
    procedural_schema = s1000d_schema._find_dm_xsd("4.1", "procedural")
    ipd_schema = s1000d_schema._find_dm_xsd("4.2", "ipd")
    assert descriptive_schema is not None and descriptive_schema.name == "descript.xsd"
    assert procedural_schema is not None and procedural_schema.name == "proced.xsd"
    assert ipd_schema is not None and ipd_schema.name == "ipd.xsd"


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


def test_default_header_business_values_are_reported_as_provisional() -> None:
    root = _root()
    resolve(root)
    xml = serialize(
        root,
        issue="4.2",
        dm_type="descriptive",
        dm_metadata={"dmc": "DMC-WEG-A-00-00-00-00A-040A-D"},
    )

    missing = missing_data_fields(xml)
    assert any("securityClassification" in field and "provisoire" in field for field in missing)
    assert any("dataHandling" in field for field in missing)
    assert any("languageIsoCode" in field and "provisoire" in field for field in missing)
    assert any("techName" in field and "provisoire" in field for field in missing)
    assert any("infoName" in field and "provisoire" in field for field in missing)


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


def test_compiled_xsd_is_reused_for_validations_in_the_same_thread(monkeypatch) -> None:
    root = _root()
    resolve(root)
    xml = serialize(
        root,
        issue="4.2",
        dm_type="descriptive",
        dm_metadata={"dmc": "DMC-WEG-A-00-00-00-00A-040A-D"},
    )
    cached_schemas = getattr(s1000d_schema._SCHEMA_CACHE, "schemas", None)
    if cached_schemas is not None:
        cached_schemas.clear()
    original_compiler = s1000d_schema.etree.XMLSchema
    compile_count = 0

    def count_compilation(document):
        nonlocal compile_count
        compile_count += 1
        return original_compiler(document)

    monkeypatch.setattr(s1000d_schema.etree, "XMLSchema", count_compilation)
    for _ in range(2):
        violations = s1000d_schema.validate_xsd(
            xml, "4.2", dm_type="descriptive", allow_internal_dtd=True,
        )
        assert not [item for item in violations if item["severity"] == "error"], violations

    assert compile_count == 1


def test_generated_outputs_validate_for_all_local_issue_and_dm_type_pairs() -> None:
    info_codes = {"descriptive": "040", "procedural": "520", "ipd": "941"}
    for issue in ("4.1", "4.2"):
        for dm_type, info_code in info_codes.items():
            diagnostics = SerializationDiagnostics()
            xml = serialize(
                IRNode(id="empty", kind="section"),
                issue=issue,
                dm_type=dm_type,
                dm_metadata={"dmc": f"DMC-WEG-A-00-00-00-00A-{info_code}A-D"},
                diagnostics=diagnostics,
            )
            violations = s1000d_schema.validate_xsd(
                xml, issue, dm_type=dm_type, allow_internal_dtd=True,
            )

            assert "TODO" not in xml
            assert not [item for item in violations if item["severity"] == "error"], (issue, dm_type, violations)
            assert diagnostics.xsd_violations == [], (issue, dm_type, diagnostics.xsd_violations)
            doc = xml_safe.fromstring(xml, allow_internal_dtd=True)
            if dm_type == "ipd":
                assert doc.find("./content/illustratedPartsCatalog/catalogSeqNumber") is not None
                assert doc.find("./content/description") is None
                assert diagnostics.provisional_fields
            elif dm_type == "procedural":
                assert doc.find("./content/procedure/mainProcedure") is not None
            else:
                assert doc.find("./content/description") is not None


def test_large_descriptive_levelled_para_has_bounded_match_states(monkeypatch) -> None:
    children = [
        IRNode(id=f"paragraph-{index}", kind="paragraph", text=f"Texte {index}.")
        for index in range(23)
    ]
    children.extend(
        IRNode(
            id=f"warning-{index}",
            kind="admonition",
            admonition="warning",
            text=f"Attention {index}.",
        )
        for index in range(8)
    )
    children.extend(
        IRNode(
            id=f"table-{index}",
            kind="table",
            table_rows=[[f"En-tete {index}"], [f"Valeur {index}"]],
        )
        for index in range(4)
    )
    children.extend(
        IRNode(id=f"figure-{index}", kind="figure", text=f"Figure {index}", icn=f"figure-{index}.jpg")
        for index in range(3)
    )
    children.extend(
        IRNode(
            id=f"section-{index}",
            kind="section",
            level=2,
            text=f"{index} Sous-section",
            children=[IRNode(id=f"nested-{index}", kind="paragraph", text=f"Sous-texte {index}.")],
        )
        for index in range(2)
    )
    children.append(IRNode(
        id="list",
        kind="item-sequence",
        form="bullet",
        children=[IRNode(id="list-item", kind="item", text="Element de liste")],
    ))
    root = IRNode(id="root", kind="section", level=0, children=[IRNode(
        id="main-section", kind="section", level=1, text="Section principale", children=children,
    )])
    resolve(root)

    model = load_xsd_model("4.2", "descriptive")
    original_prune = model._prune_matches
    prune_calls = 0

    def count_prunes(matches):
        nonlocal prune_calls
        prune_calls += 1
        return original_prune(matches)

    monkeypatch.setattr(model, "_prune_matches", count_prunes)
    xml = serialize(
        root,
        issue="4.2",
        dm_type="descriptive",
        dm_metadata={"dmc": "DMC-WEG-A-00-00-00-00A-040A-D"},
    )
    violations = s1000d_schema.validate_xsd(
        xml, "4.2", dm_type="descriptive", allow_internal_dtd=True,
    )
    doc = xml_safe.fromstring(xml, allow_internal_dtd=True)
    level = doc.find("./content/description/levelledPara")

    assert prune_calls < 50_000
    assert not [item for item in violations if item["severity"] == "error"], violations
    assert level is not None
    assert sum(
        "Texte " in "".join(paragraph.itertext())
        for paragraph in level.findall("./para")
    ) == 23
    assert level.find("./para/randomList") is not None
    assert len(level.findall("./warning")) == 8
    assert len(level.findall("./table")) == 4
    assert len(level.findall("./figure")) == 3
    assert len(level.findall("./levelledPara")) == 2


def test_ipd_unmapped_source_remains_downloadable_and_is_reported() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="p", kind="paragraph", text="Texte source sans references de pieces."),
    ])
    diagnostics = SerializationDiagnostics()
    xml = serialize(
        root,
        issue="4.2",
        dm_type="ipd",
        dm_metadata={"dmc": "DMC-WEG-A-00-00-00-00A-941A-D"},
        diagnostics=diagnostics,
    )
    doc = xml_safe.fromstring(xml, allow_internal_dtd=True)

    assert "Texte source sans references de pieces." not in xml
    assert doc.find("./content/illustratedPartsCatalog") is not None
    assert any("Aucun mapping IPD" in issue["message"] for issue in diagnostics.xsd_violations)
    assert not [
        violation for violation in s1000d_schema.validate_xsd(
            xml, "4.2", dm_type="ipd", allow_internal_dtd=True,
        ) if violation["severity"] == "error"
    ]


def test_model_orders_children_and_enforces_cardinality_and_parent_rules() -> None:
    root = _root()
    resolve(root)
    xml = serialize(
        root,
        issue="4.2",
        dm_type="descriptive",
        dm_metadata={"dmc": "DMC-WEG-A-00-00-00-00A-040A-D"},
    )
    doc = xml_safe.fromstring(xml, allow_internal_dtd=True)
    content = doc.find("content")
    assert content is not None
    doc.remove(content)
    doc.insert(0, content)
    doc.append(deepcopy(content))
    para = doc.find(".//para")
    assert para is not None
    forbidden = para.makeelement("proceduralStep")
    forbidden.text = "Ne pas emettre ici."
    para.append(forbidden)

    report = load_xsd_model("4.2", "descriptive").constrain(doc)
    child_names = [child.tag for child in doc if isinstance(child.tag, str)]

    assert child_names == ["identAndStatusSection", "content"]
    assert len(doc.findall("content")) == 1
    assert doc.find(".//proceduralStep") is None
    assert any("cardinalite" in item["message"] for item in report.violations)
    assert any("proceduralStep" in item["message"] and "pas autorise" in item["message"] for item in report.violations)


def test_xsd_model_uses_real_patterns_and_enumerations() -> None:
    model = load_xsd_model("4.2", "descriptive")
    model_code_type = (None, "modelIdentCodeAttType")
    location_code_type = (None, "itemLocationCodeAttType")
    model_code_facets = model.facets_for(model_code_type)
    location_facets = model.facets_for(location_code_type)

    assert "[A-Z0-9]{2,14}" in model_code_facets.patterns
    assert model.accepts_value(model_code_type, "WEG")
    assert not model.accepts_value(model_code_type, "W")
    assert not model.accepts_value(model_code_type, "A" * 15)
    assert location_facets.enumerations == ("A", "B", "C", "D", "T")
    assert model.accepts_value(location_code_type, "T")
    assert not model.accepts_value(location_code_type, "X")


def test_invalid_dmc_pattern_and_enumeration_use_xsd_accepted_provisionals() -> None:
    root = _root()
    resolve(root)
    diagnostics = SerializationDiagnostics()
    xml = serialize(
        root,
        issue="4.2",
        dm_type="descriptive",
        dm_metadata={
            "dmc": "DMC-WEG-A-00-00-00-00A-040A-D",
            "model_ident_code": "A" * 15,
            "item_location_code": "X",
        },
        diagnostics=diagnostics,
    )
    doc = xml_safe.fromstring(xml, allow_internal_dtd=True)
    code = doc.find("./identAndStatusSection/dmAddress/dmIdent/dmCode")
    assert code is not None

    assert code.get("modelIdentCode") == "ZZ"
    assert code.get("itemLocationCode") == "A"
    assert any("@modelIdentCode" in field and "provisoire" in field for field in missing_data_fields(xml))
    assert any("@itemLocationCode" in field and "provisoire" in field for field in missing_data_fields(xml))
    assert any("modelIdentCode" in item["path"] for item in diagnostics.xsd_violations)
    assert not [
        violation for violation in s1000d_schema.validate_xsd(
            xml, "4.2", dm_type="descriptive", allow_internal_dtd=True,
        ) if violation["severity"] == "error"
    ]
