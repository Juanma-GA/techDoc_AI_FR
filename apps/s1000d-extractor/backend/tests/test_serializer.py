"""Serialiseur : l'arbre resolu produit les bons elements S1000D."""

from __future__ import annotations

from app.core import xml_safe
from app.core.dmrl import DmrlEntry
from app.core.ir import IRNode
from app.core.resolver import resolve
from app.core.s1000d_serializer import clean_title, serialize


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
    return serialize(root, issue="5.0", dm_type=dm_type)


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


def test_banner_and_todo_placeholders() -> None:
    xml = _doc()
    assert "NON valide comme Data Module" in xml
    assert "brexDmRef" in xml and "identAndStatusSection" in xml
    assert "infoEntityIdent" not in xml or "ICN-TODO" in xml  # graphics: infoEntityIdent only


def test_output_is_wellformed() -> None:
    _parse(_doc())  # ne leve pas


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
    xml = serialize(root, issue="5.0", dm_type="descriptive")
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
    xml = serialize(root, issue="5.0", dm_type="descriptive")
    assert 'infoEntityIdent="figure-1-pump"' in xml
    assert "ICN-TODO" not in xml


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

    xml = serialize(root, issue="5.0", dm_type="description")

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
        issue="5.0",
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
    xml = serialize(root, issue="5.0", dm_type="descriptive", title="4.1. LEVAGE")
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
    xml = serialize(root, issue="5.0", dm_type="descriptive")

    assert '<!DOCTYPE dmodule [' in xml
    assert '<!ENTITY ICN-ONE SYSTEM "ICN-ONE.JPG" NDATA jpg>' in xml
    assert '<!ENTITY ICN-TWO SYSTEM "ICN-TWO.png" NDATA png>' in xml
    assert "%ISOEntities;" in xml
    assert xml.index("<!DOCTYPE") < xml.index("<dmodule")


def test_internal_ref_emitted() -> None:
    root = IRNode(id="r", kind="section", level=0)
    root.children = [IRNode(
        id="p", kind="paragraph", form="prose", context="descriptive",
        text="Voir figure 3 pour le detail.",
        refs=[{"kind": "internal", "target_kind": "figure", "target": "3",
               "text": "Voir figure 3"}],
    )]
    resolve(root)
    xml = serialize(root, issue="5.0", dm_type="descriptive")
    assert "internalRef" in xml
    doc = _parse(xml)
    ref = doc.find(".//internalRef")
    assert ref is not None
    assert ref.get("internalRefTargetType") == "figure"
