"""Serialiseur : l'arbre resolu produit les bons elements S1000D."""

from __future__ import annotations

import pytest

from app.core import xml_safe
from lxml import etree
from app.core.dmrl import DmrlEntry
from app.core.ir import IRNode, InlineRun, from_dict, to_dict
from app.core.resolver import resolve
from app.core.s1000d_schema import validate_xsd
from app.core.s1000d_serializer import build_reference_index, clean_title, missing_data_fields, serialize
from app.core.structure_heuristics import detect_refs


def _doc(dm_type: str = "descriptive") -> str:
    root = IRNode(id="r", kind="section", level=0)
    sec = IRNode(id="s1", kind="section", text="Description", level=1, context="descriptive")
    sec.children = [
        IRNode(id="p1", kind="paragraph", form="prose", text="Texte.", context="descriptive"),
        IRNode(id="a1", kind="admonition", admonition="warning", text="Danger.", context="descriptive"),
        IRNode(id="a2", kind="admonition", admonition="note", text="Info.", context="descriptive"),
        IRNode(id="t1", kind="table", form="table", table_rows=[["A", "B"], ["1", "2"]]),
    ]
    lst = IRNode(id="l1", kind="item-sequence", form="bullet", context="descriptive")
    lst.children = [IRNode(id="i1", kind="item", text="Un"), IRNode(id="i2", kind="item", text="Deux")]
    sec.children.append(lst)
    root.children = [sec]
    resolve(root)
    return serialize(root, issue="4.2", dm_type=dm_type)


def _serialize_with_dmc(root: IRNode, issue: str, dm_type: str) -> str:
    info_code = {"descriptive": "040", "procedural": "520", "ipd": "941"}[dm_type]
    return serialize(
        root,
        issue=issue,
        dm_type=dm_type,
        dm_metadata={"dmc": f"DMC-WEG-A-00-00-00-00A-{info_code}A-D"},
    )


def test_issue_5_0_is_not_a_generation_target() -> None:
    with pytest.raises(ValueError, match="Generation XSD non disponible"):
        serialize(IRNode(id="root", kind="section"), issue="5.0", dm_type="descriptive")


def _parse(xml: str):
    return xml_safe.fromstring(xml, allow_internal_dtd=True)


def test_descriptive_elements_present() -> None:
    xml = _doc("descriptive")
    doc = _parse(xml)
    tags = {el.tag for el in doc.iter()}
    for expected in ("description", "levelledPara", "para", "warning",
                     "warningAndCautionPara", "note", "notePara",
                     "randomList", "listItem", "table", "tgroup", "entry"):
        assert expected in tags, f"manque {expected}"


def test_procedural_wraps_in_mainprocedure() -> None:
    xml = _doc("procedural")
    doc = _parse(xml)
    tags = {el.tag for el in doc.iter()}
    assert "procedure" in tags and "mainProcedure" in tags


def test_empty_main_procedure_gets_xsd_valid_replacement_step() -> None:
    root = IRNode(id="root", kind="section", level=0)
    xml = _serialize_with_dmc(root, "4.2", "procedural")

    doc = _parse(xml)
    main = doc.find("./content/procedure/mainProcedure")
    assert main is not None
    assert main.findtext("./proceduralStep/title") == "Etape a renseigner"
    assert "Etape de procedure a completer a partir de la source." in "".join(main.itertext())
    assert "A REMPLACER AVANT PUBLICATION" in xml
    assert "TODO" not in xml
    violations = validate_xsd(xml, "4.2", dm_type="procedural", allow_internal_dtd=True)
    assert not [violation for violation in violations if violation["severity"] == "error"], violations


def test_banner_and_missing_data_summary() -> None:
    xml = _doc()
    assert "Squelette structurel best-effort" in xml
    assert "brexDmRef" in xml and "identAndStatusSection" in xml
    assert "A REMPLACER AVANT PUBLICATION" in xml
    assert "TODO" not in xml
    assert "infoEntityIdent" not in xml or "ICN-ZZZ-00000" in xml


def test_output_is_wellformed() -> None:
    _parse(_doc())  # ne leve pas


def test_inline_bold_uses_normalized_emphasis_code() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(
            id="p",
            kind="paragraph",
            text="Texte normal mot important.",
            context="descriptive",
            inline_runs=[
                InlineRun("Texte normal "),
                InlineRun("mot important", bold=True),
                InlineRun("."),
            ],
        ),
    ])
    resolve(root)
    xml = serialize(root, issue="4.2", dm_type="descriptive")
    doc = _parse(xml)
    emphasis = doc.find(".//para/emphasis")

    assert emphasis is not None
    assert emphasis.get("emphasisType") == "em01"
    assert "".join(doc.find(".//para").itertext()) == "Texte normal mot important."


def test_inline_bold_italic_uses_nested_emphasis_and_validates() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[IRNode(
        id="p",
        kind="paragraph",
        text="Remarque",
        context="descriptive",
        inline_runs=[InlineRun("Remarque", bold=True, italic=True)],
    )])
    resolve(root)
    xml = _serialize_with_dmc(root, "4.2", "descriptive")
    doc = _parse(xml)
    outer = doc.find(".//para/emphasis")

    assert outer is not None and outer.get("emphasisType") == "em01"
    inner = outer.find("./emphasis")
    assert inner is not None and inner.get("emphasisType") == "em02"
    assert inner.text == "Remarque"
    violations = validate_xsd(xml, "4.2", dm_type="descriptive", allow_internal_dtd=True)
    assert not [violation for violation in violations if violation["severity"] == "error"], violations


def test_italic_colon_stays_inside_outer_bold_emphasis() -> None:
    note = IRNode(
        id="note",
        kind="admonition",
        admonition="note",
        text="Remarque\u00a0:",
        inline_runs=[
            InlineRun("Remarque", bold=True, italic=True),
            InlineRun("\u00a0:", italic=True),
        ],
    )
    root = IRNode(id="r", kind="section", level=0, children=[note])
    resolve(root)
    xml = _serialize_with_dmc(root, "4.2", "descriptive")
    doc = _parse(xml)
    outer = doc.find(".//note/notePara/emphasis")

    assert outer is not None and outer.get("emphasisType") == "em01"
    inner = outer.find("./emphasis")
    assert inner is not None and inner.get("emphasisType") == "em02"
    assert inner.text == "Remarque"
    assert inner.tail == "\u00a0:"
    violations = validate_xsd(xml, "4.2", dm_type="descriptive", allow_internal_dtd=True)
    assert not [violation for violation in violations if violation["severity"] == "error"], violations


def test_ordered_note_items_use_s1000d_attention_list() -> None:
    sequence = IRNode(id="list", kind="item-sequence", form="ordered", children=[
        IRNode(id="item-1", kind="item", text="Ne superposez pas."),
        IRNode(id="item-2", kind="item", text="Alignez les caisses."),
    ])
    note = IRNode(
        id="note", kind="admonition", admonition="note", text="Remarque :",
        children=[sequence],
    )
    root = IRNode(id="r", kind="section", level=0, children=[note])
    resolve(root)
    xml = _serialize_with_dmc(root, "4.2", "descriptive")
    doc = _parse(xml)
    items = doc.findall(
        ".//note/attentionSequentialList/attentionSequentialListItem/attentionListItemPara"
    )

    assert ["".join(item.itertext()) for item in items] == [
        "Ne superposez pas.",
        "Alignez les caisses.",
    ]
    violations = validate_xsd(xml, "4.2", dm_type="descriptive", allow_internal_dtd=True)
    assert not [violation for violation in violations if violation["severity"] == "error"], violations


def test_nested_lettered_list_serializes_inside_numbered_item() -> None:
    letters = IRNode(
        id="letters",
        kind="item-sequence",
        form="lettered",
        children=[
            IRNode(id="letter-a", kind="item", text="a. Premier sous-item."),
            IRNode(id="letter-b", kind="item", text="b. Deuxième sous-item."),
        ],
    )
    numbered = IRNode(
        id="numbered",
        kind="item-sequence",
        form="ordered",
        children=[
            IRNode(id="number-1", kind="item", text="Premier item."),
            IRNode(id="number-2", kind="item", text="Second item.", children=[letters]),
            IRNode(id="number-3", kind="item", text="Troisième item."),
        ],
    )
    root = IRNode(id="r", kind="section", level=0, children=[numbered])
    resolve(root)
    xml = _serialize_with_dmc(root, "4.2", "descriptive")
    doc = _parse(xml)
    nested_items = doc.findall(
        ".//sequentialList/listItem/para/randomList/listItem/para"
    )

    assert ["".join(item.itertext()) for item in nested_items] == [
        "a. Premier sous-item.",
        "b. Deuxième sous-item.",
    ]
    violations = validate_xsd(xml, "4.2", dm_type="descriptive", allow_internal_dtd=True)
    assert not [violation for violation in violations if violation["severity"] == "error"], violations


def test_inline_runs_survive_ir_json_round_trip() -> None:
    node = IRNode(
        id="p",
        kind="paragraph",
        text="Texte gras",
        inline_runs=[InlineRun("Texte "), InlineRun("gras", bold=True)],
    )

    restored = from_dict(to_dict(node))

    assert restored.inline_runs[1].text == "gras"
    assert restored.inline_runs[1].bold is True


def test_header_is_completed_from_dmrl_metadata() -> None:
    entry = DmrlEntry(
        dmc="DMC-WEG-A-00-00-00-00A-001A-A",
        title="Moteur electrique",
        tech_name="Moteur electrique",
        info_name="Description",
        dm_type="procedural",
    )
    xml = serialize(
        IRNode(id="r", kind="section"),
        issue="4.1",
        dm_type=entry.dm_type,
        title=entry.title,
        dm_metadata=entry.to_dict(),
    )
    assert "S1000D_4-1/xml_schema_flat/proced.xsd" in xml
    assert 'modelIdentCode="WEG"' in xml
    assert "<techName>Moteur electrique</techName>" in xml
    assert "<infoName>Description</infoName>" in xml
    assert "<dmStatus issueType=\"new\">" in xml
    assert xml.index("</identAndStatusSection>") < xml.index("<content>")


def test_table_header_becomes_thead_and_colspec() -> None:
    root = IRNode(id="r", kind="section", level=0)
    root.children = [IRNode(
        id="t", kind="table", form="table",
        table_rows=[["Bolt", "Torque"], ["M6", "12"]],
        table_header=["Bolt", "Torque"],
    )]
    resolve(root)
    xml = serialize(root, issue="4.2", dm_type="descriptive")
    doc = _parse(xml)
    tags = {el.tag for el in doc.iter()}
    assert "thead" in tags and "tbody" in tags and "colspec" in tags
    # L'entete ne doit pas etre repetee dans le corps.
    tbody = doc.find(".//tbody")
    body_cells = [e.findtext("para") for e in tbody.iter("entry")]
    assert "M6" in body_cells and "Bolt" not in body_cells


def test_figure_icn_referenced() -> None:
    root = IRNode(id="r", kind="section", level=0)
    root.children = [IRNode(id="f", kind="figure", form="caption",
                            text="Figure 1", icn="figure-1-pump.jpg")]
    resolve(root)
    xml = serialize(root, issue="4.2", dm_type="descriptive")
    assert 'infoEntityIdent="figure-1-pump"' in xml
    assert "ICN-ZZZ-00000" not in xml


def test_composite_figure_references_all_graphics() -> None:
    from app.core.ir import IRNode
    from app.core.s1000d_serializer import serialize

    root = IRNode(
        id="root",
        kind="section",
        children=[IRNode(
            id="f",
            kind="figure",
            text="Figure 5.4 Composite",
            icns=["figure-5-4-composite.jpg", "figure-5-4-composite-2.jpg"],
        )],
    )

    xml = serialize(root, issue="4.2", dm_type="description")

    assert xml.count("<graphic ") == 2
    assert 'infoEntityIdent="figure-5-4-composite"' in xml
    assert 'infoEntityIdent="figure-5-4-composite-2"' in xml


def test_figures_and_tables_have_incremental_ids() -> None:
    root = IRNode(id="r", kind="section", level=0)
    root.children = [
        IRNode(id="f1", kind="figure", text="Figure 1 First"),
        IRNode(id="t1", kind="table", table_rows=[["A"]]),
        IRNode(id="f2", kind="figure", text="Figure 2 Second"),
        IRNode(id="t2", kind="table", table_rows=[["B"]]),
    ]
    xml = serialize(
        root,
        issue="4.2",
        dm_type="descriptive",
        figure_offset=4,
        table_offset=7,
    )

    assert '<figure id="fig-0005">' in xml
    assert '<figure id="fig-0006">' in xml
    assert '<table id="tbl-0008">' in xml
    assert '<table id="tbl-0009">' in xml


def test_final_titles_drop_editorial_numbering() -> None:
    root = IRNode(id="r", kind="section", level=0)
    root.children = [
        IRNode(
            id="s1",
            kind="section",
            text="4.1. LEVAGE",
            children=[IRNode(
                id="f", kind="figure",
                text="Figure 4.1 \u2013 Serrage correct de l\u2019anneau de levage",
            )],
        ),
    ]
    xml = serialize(root, issue="4.2", dm_type="descriptive", title="4.1. LEVAGE")
    doc = _parse(xml)

    assert clean_title("4.1. LEVAGE") == "LEVAGE"
    assert doc.findtext(".//levelledPara/title") == "LEVAGE"
    assert doc.findtext(".//figure/title") == "Serrage correct de l\u2019anneau de levage"
    assert "Figure 4.1" not in xml


def test_figure_icns_are_declared_in_doctype() -> None:
    root = IRNode(id="r", kind="section", level=0)
    root.children = [
        IRNode(id="f1", kind="figure", form="caption", icn="ICN-ONE.JPG"),
        IRNode(id="f2", kind="figure", form="caption", icn="ICN-TWO.png"),
    ]
    resolve(root)
    xml = serialize(root, issue="4.2", dm_type="descriptive")

    assert '<!DOCTYPE dmodule [' in xml
    assert '<!ENTITY ICN-ONE SYSTEM "ICN-ONE.JPG" NDATA jpg>' in xml
    assert '<!ENTITY ICN-TWO SYSTEM "ICN-TWO.png" NDATA png>' in xml
    assert '<!ENTITY % ISOEntities PUBLIC "ISO 8879-1986//ENTITIES ISO Character Entities 20030531//EN//XML" "ent/ISOEntities">' in xml
    assert "%ISOEntities;" not in xml
    assert xml.index("<!DOCTYPE") < xml.index("<dmodule")


def test_iso_entities_are_declared_without_graphics_for_descriptive_and_procedural_dms() -> None:
    declaration = '<!ENTITY % ISOEntities PUBLIC "ISO 8879-1986//ENTITIES ISO Character Entities 20030531//EN//XML" "ent/ISOEntities">'

    assert declaration in _doc("descriptive")
    assert declaration in _doc("procedural")


def test_internal_ref_emitted() -> None:
    root = IRNode(id="r", kind="section", level=0)
    root.children = [IRNode(
        id="p", kind="paragraph", form="prose", context="descriptive",
        text="Voir figure 3 pour le detail.",
        refs=[{"kind": "internal", "target_kind": "figure", "target": "3",
               "text": "Voir figure 3"}],
    ), IRNode(id="f", kind="figure", text="Figure 3 - Vue")]
    resolve(root)
    xml = serialize(root, issue="4.2", dm_type="descriptive")
    assert "internalRef" in xml
    doc = _parse(xml)
    ref = doc.find(".//internalRef")
    assert ref is not None
    assert ref.get("internalRefTargetType") == "irtt01"
    assert ref.get("internalRefId") == "fig-0001"


def test_detected_refs_resolve_inline_to_real_targets() -> None:
    text = "Voir Figure 6.12 et le tableau 7.2 pour le detail."
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="p", kind="paragraph", text=text, refs=detect_refs(text)),
        IRNode(id="f", kind="figure", text="Figure 6.12 - Vue"),
        IRNode(
            id="t",
            kind="table",
            text="Tableau 7.2 - Valeurs",
            table_rows=[["A"]],
        ),
    ])
    resolve(root)
    xml = serialize(root, issue="4.2", dm_type="descriptive")
    doc = _parse(xml)

    para = doc.find(".//content//para")
    assert para is not None
    refs = para.findall("internalRef")
    assert [(ref.get("internalRefId"), ref.get("internalRefTargetType")) for ref in refs] == [
        ("fig-0001", "irtt01"),
        ("tbl-0001", "irtt02"),
    ]
    assert "".join(para.itertext()) == text
    assert not doc.xpath('.//internalRef[starts-with(@internalRefId, "TODO-")]')


def test_uri_ref_is_emitted_as_external_pub_ref() -> None:
    text = "Consulter https://example.com/doc.pdf."
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="p", kind="paragraph", text=text, refs=detect_refs(text)),
    ])
    resolve(root)
    xml = serialize(root, issue="4.2", dm_type="descriptive")
    doc = _parse(xml)

    external = doc.find(".//content//externalPubRef")
    assert external is not None
    assert external.get("{http://www.w3.org/1999/xlink}href") == "https://example.com/doc.pdf"
    assert "".join(doc.find(".//content//para").itertext()) == text  # type: ignore[union-attr]


def test_adjacent_runs_with_same_emphasis_are_merged() -> None:
    text = "Remarque : La qualification est uniquement valable pour la societe qui a forme l employe autorise et qualifie."
    root = IRNode(id="r", kind="section", level=0, children=[IRNode(
        id="note",
        kind="admonition",
        admonition="note",
        text=text,
        inline_runs=[
            InlineRun("Remarque : ", bold=True),
            InlineRun("La qualification est uniquement valable pour la societe qui a forme l employe", italic=True),
            InlineRun(" autorise et qualifie.", italic=True),
        ],
    )])
    resolve(root)
    doc = _parse(serialize(root, issue="4.2", dm_type="descriptive"))

    note_para = doc.find(".//content//note/notePara")
    assert note_para is not None
    emphases = note_para.findall("emphasis")
    assert [emphasis.get("emphasisType") for emphasis in emphases] == ["em01", "em02"]
    assert "".join(note_para.itertext()) == text


def test_cross_dm_ref_uses_target_dmc() -> None:
    source_text = "Voir Figure 2 pour le detail."
    source = IRNode(id="source", kind="section", level=0, children=[
        IRNode(id="p", kind="paragraph", text=source_text, refs=detect_refs(source_text)),
    ])
    target = IRNode(id="target", kind="section", level=0, children=[
        IRNode(id="f", kind="figure", text="Figure 2 - Vue"),
    ])
    resolve(source)
    resolve(target)
    index = build_reference_index([
        ("dm1", source, {"dmc": "DMC-TEST-A-00-00-00-00A-040A-D"}),
        ("dm2", target, {"dmc": "DMC-TEST-A-00-00-00-00A-520A-D"}),
    ])
    xml = serialize(
        source,
        issue="4.2",
        dm_type="descriptive",
        reference_index=index,
        reference_dm_id="dm1",
    )
    doc = _parse(xml)

    dm_ref = doc.find(".//content//para/dmRef")
    assert dm_ref is not None
    assert dm_ref.get("referredFragment") == "fig-0001"
    assert dm_ref.find("./dmRefIdent/dmCode").get("modelIdentCode") == "TEST"  # type: ignore[union-attr]
    assert dm_ref.find("./dmRefIdent/dmCode").get("infoCode") == "520"  # type: ignore[union-attr]
    assert "".join(doc.find(".//content//para").itertext()) == source_text  # type: ignore[union-attr]


def test_cross_dm_ref_emits_weg_dm_code():
    source_text = "Voir Figure 2 pour le detail."
    source = IRNode(id="source", kind="section", level=0, children=[
        IRNode(id="p", kind="paragraph", text=source_text, refs=detect_refs(source_text)),
    ])
    target = IRNode(id="target", kind="section", level=0, children=[
        IRNode(id="f", kind="figure", text="Figure 2 - Vue"),
    ])
    resolve(source)
    resolve(target)
    index = build_reference_index([
        ("dm1", source, {"dmc": "DMC-TEST-A-00-00-00-00A-040A-D"}),
        ("dm2", target, {"dmc": "DMC-WEG-AA-00-09-00-00A-040A-A"}),
    ])
    doc = _parse(serialize(
        source,
        issue="4.2",
        dm_type="descriptive",
        reference_index=index,
        reference_dm_id="dm1",
    ))

    dm_code = doc.find(".//content//para/dmRef/dmRefIdent/dmCode")
    assert dm_code is not None
    assert dm_code.get("modelIdentCode") == "WEG"
    assert dm_code.get("systemDiffCode") == "AA"
    assert dm_code.get("systemCode") == "00"
    assert dm_code.get("subSystemCode") == "0"
    assert dm_code.get("subSubSystemCode") == "9"


def test_sections_use_sequential_par_ids() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="s1", kind="section", text="1 First", level=1, children=[
            IRNode(id="s11", kind="section", text="1.1 Nested", level=2),
        ]),
    ])
    resolve(root)
    doc = _parse(serialize(root, issue="4.2", dm_type="descriptive"))

    sections = doc.findall(".//content//levelledPara")
    assert [section.get("id") for section in sections] == ["par-0001", "par-0002"]
    assert not doc.xpath('.//*[@id="sec-n69"]')


def test_serializer_excludes_layout_noise_zones() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="header", kind="paragraph", text="www.example.test", zone="header"),
        IRNode(id="toc", kind="paragraph", text="FRANCAIS", zone="toc"),
        IRNode(id="s1", kind="section", text="1 First", level=1, children=[
            IRNode(id="body", kind="paragraph", text="Definitions."),
            IRNode(id="footer", kind="paragraph", text="Page 1", zone="footer"),
        ]),
    ])
    resolve(root)
    xml = serialize(root, issue="4.2", dm_type="descriptive")

    assert "www.example.test" not in xml
    assert "FRANCAIS" not in xml
    assert "Page 1" not in xml
    assert "Definitions." in xml


def test_descriptive_output_respects_issue_4_1_content_model() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[IRNode(
        id="s",
        kind="section",
        level=1,
        text="1 Test",
        children=[
            IRNode(id="p", kind="paragraph", text="Blablabla :"),
            IRNode(
                id="l",
                kind="item-sequence",
                form="bullet",
                children=[IRNode(id="i", kind="item", text="Item")],
            ),
            IRNode(id="w", kind="admonition", admonition="warning", text="Attention."),
        ],
    )])
    resolve(root)
    xml = _serialize_with_dmc(root, "4.1", "descriptive")
    violations = validate_xsd(xml, "4.1", dm_type="descriptive", allow_internal_dtd=True)

    assert not [violation for violation in violations if violation["severity"] == "error"]
    doc = _parse(xml)
    level = doc.find(".//content//levelledPara")
    assert level is not None
    assert [child.tag for child in level if not isinstance(child, etree._Comment)] == [
        "title", "warning", "para",
    ]
    assert level.find("./para/randomList") is not None


def test_warnings_precede_cautions_in_issue_4_1() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[IRNode(
        id="s",
        kind="section",
        level=1,
        text="1 Safety",
        children=[
            IRNode(id="w1", kind="admonition", admonition="warning", text="W1."),
            IRNode(id="c", kind="admonition", admonition="caution", text="C."),
            IRNode(id="w2", kind="admonition", admonition="warning", text="W2."),
        ],
    )])
    resolve(root)
    xml = _serialize_with_dmc(root, "4.1", "descriptive")
    violations = validate_xsd(xml, "4.1", dm_type="descriptive", allow_internal_dtd=True)

    assert not [violation for violation in violations if violation["severity"] == "error"]
    doc = _parse(xml)
    level = doc.find(".//content//levelledPara")
    assert level is not None
    assert [child.tag for child in level if child.tag in {"warning", "caution"}] == [
        "warning", "warning", "caution",
    ]


def test_procedural_output_respects_issue_4_1_content_model() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[IRNode(
        id="s",
        kind="section",
        level=1,
        text="1 Procedure",
        context="procedural",
        children=[
            IRNode(id="w", kind="admonition", admonition="warning", text="Attention."),
            IRNode(id="p", kind="paragraph", text="Faire."),
        ],
    )])
    resolve(root)
    xml = _serialize_with_dmc(root, "4.1", "procedural")
    violations = validate_xsd(xml, "4.1", dm_type="procedural", allow_internal_dtd=True)

    assert not [violation for violation in violations if violation["severity"] == "error"]


def test_procedural_requirements_are_structured_before_main_steps() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(
            id="conditions", kind="section", level=1,
            text="Conditions préalables", context="procedural",
            children=[IRNode(
                id="condition", kind="paragraph",
                text="Isoler la batterie.", context="procedural",
            )],
        ),
        IRNode(
            id="personnel", kind="section", level=1,
            text="Personnel requis", context="procedural",
            children=[IRNode(
                id="trade", kind="paragraph",
                text="Deux techniciens qualifiés.", context="procedural",
            )],
        ),
        IRNode(
            id="tools", kind="section", level=1,
            text="Outillage nécessaire", context="procedural",
            children=[IRNode(
                id="tool-list", kind="item-sequence", form="bullet",
                children=[IRNode(id="tool", kind="item", text="Tournevis cruciforme")],
            )],
        ),
        IRNode(
            id="supplies", kind="section", level=1,
            text="Consommables", context="procedural",
            children=[IRNode(
                id="supply", kind="paragraph",
                text="Huile hydraulique.", context="procedural",
            )],
        ),
        IRNode(
            id="spares", kind="section", level=1,
            text="Pièces de rechange", context="procedural",
            children=[IRNode(
                id="spare", kind="paragraph",
                text="Joint torique.", context="procedural",
            )],
        ),
        IRNode(
            id="safety", kind="section", level=1,
            text="Sécurité", context="procedural",
            children=[
                IRNode(
                    id="warning", kind="admonition", admonition="warning",
                    text="Risque de projection.",
                ),
                IRNode(
                    id="safety-note", kind="paragraph",
                    text="Porter des lunettes de protection.",
                    context="procedural",
                ),
            ],
        ),
        IRNode(
            id="step", kind="section", level=1,
            text="Remplacement", context="procedural",
            children=[IRNode(
                id="action", kind="paragraph",
                text="Déposer le capot.", context="procedural",
            )],
        ),
    ])
    resolve(root)
    xml = _serialize_with_dmc(root, "4.2", "procedural")
    violations = validate_xsd(
        xml, "4.2", dm_type="procedural", allow_internal_dtd=True,
    )

    assert not [violation for violation in violations if violation["severity"] == "error"], violations
    doc = _parse(xml)
    preliminary = doc.find("./content/procedure/preliminaryRqmts")
    assert preliminary is not None
    assert preliminary.findtext("./reqCondGroup/reqCondNoRef/reqCond") == "Isoler la batterie."
    assert preliminary.findtext("./reqPersons/personnel/trade") == "Deux techniciens qualifiés."
    assert preliminary.findtext("./reqSupportEquips/supportEquipDescrGroup/supportEquipDescr/name") == "Tournevis cruciforme"
    assert preliminary.findtext("./reqSupplies/supplyDescrGroup/supplyDescr/name") == "Huile hydraulique."
    assert preliminary.findtext("./reqSpares/spareDescrGroup/spareDescr/name") == "Joint torique."
    assert preliminary.findtext("./reqSafety/safetyRqmts/warning/warningAndCautionPara") == "Risque de projection."
    assert preliminary.findtext("./reqSafety/safetyRqmts/note/notePara") == "Porter des lunettes de protection."
    for quantity in preliminary.findall(".//reqQuantity"):
        assert quantity.text == "A REMPLACER"
        assert quantity.get("unitOfMeasure") == "A REMPLACER"
    assert "TODO" not in xml

    main_steps = doc.find("./content/procedure/mainProcedure")
    assert main_steps is not None
    assert "Déposer le capot." in "".join(main_steps.itertext())
    assert "Tournevis cruciforme" not in "".join(main_steps.itertext())


def test_nested_preliminary_requirements_are_removed_from_main_procedure() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(
            id="preliminary", kind="section", level=1,
            text="Preliminary Requirements", context="procedural",
            children=[IRNode(
                id="tools", kind="section", level=2,
                text="Tools Required", context="procedural",
                children=[IRNode(
                    id="tool-list", kind="item-sequence", form="bullet",
                    children=[IRNode(id="tool", kind="item", text="Torque wrench")],
                )],
            )],
        ),
        IRNode(
            id="step", kind="section", level=1,
            text="Adjustment", context="procedural",
            children=[IRNode(
                id="action", kind="paragraph",
                text="Adjust the nut.", context="procedural",
            )],
        ),
    ])
    resolve(root)
    xml = _serialize_with_dmc(root, "4.2", "procedural")
    violations = validate_xsd(
        xml, "4.2", dm_type="procedural", allow_internal_dtd=True,
    )

    assert not [violation for violation in violations if violation["severity"] == "error"], violations
    doc = _parse(xml)
    assert doc.findtext(
        "./content/procedure/preliminaryRqmts/reqSupportEquips/"
        "supportEquipDescrGroup/supportEquipDescr/name"
    ) == "Torque wrench"
    main = doc.find("./content/procedure/mainProcedure")
    assert main is not None
    assert "Torque wrench" not in "".join(main.itertext())
    assert "Adjust the nut." in "".join(main.itertext())


def test_missing_preliminary_requirements_do_not_create_todo_values() -> None:
    root = IRNode(id="r", kind="section", level=0, children=[IRNode(
        id="step", kind="paragraph", text="Effectuer le contrôle.", context="procedural",
    )])
    resolve(root)
    xml = _serialize_with_dmc(root, "4.2", "procedural")
    violations = validate_xsd(
        xml, "4.2", dm_type="procedural", allow_internal_dtd=True,
    )

    assert not [violation for violation in violations if violation["severity"] == "error"], violations
    doc = _parse(xml)
    preliminary = doc.find("./content/procedure/preliminaryRqmts")
    assert preliminary is not None
    assert preliminary.find("./reqCondGroup/noConds") is not None
    assert preliminary.find("./reqSupportEquips/noSupportEquips") is not None
    assert preliminary.find("./reqSupplies/noSupplies") is not None
    assert preliminary.find("./reqSpares/noSpares") is not None
    assert preliminary.find("./reqSafety/noSafety") is not None
    assert preliminary.find("./reqPersons") is None
    assert not any("preliminaryRqmts" in field for field in missing_data_fields(xml))
    assert "TODO" not in etree.tostring(preliminary, encoding="unicode")
