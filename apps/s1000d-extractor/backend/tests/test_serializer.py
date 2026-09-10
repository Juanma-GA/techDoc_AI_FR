"""Serialiseur : l'arbre resolu produit les bons elements S1000D."""

from __future__ import annotations

from lxml import etree

from app.core.ir import IRNode
from app.core.resolver import resolve
from app.core.s1000d_serializer import serialize


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


def test_descriptive_elements_present() -> None:
    xml = _doc("descriptive")
    doc = etree.fromstring(xml.encode("utf-8"))
    tags = {el.tag for el in doc.iter()}
    for expected in ("description", "levelledPara", "para", "warning",
                     "warningAndCautionPara", "note", "notePara",
                     "randomList", "listItem", "table", "tgroup", "entry"):
        assert expected in tags, f"manque {expected}"


def test_procedural_wraps_in_mainprocedure() -> None:
    xml = _doc("procedural")
    doc = etree.fromstring(xml.encode("utf-8"))
    tags = {el.tag for el in doc.iter()}
    assert "procedure" in tags and "mainProcedure" in tags


def test_banner_and_todo_placeholders() -> None:
    xml = _doc()
    assert "NON valide comme Data Module" in xml
    assert "brexDmRef" in xml and "identAndStatusSection" in xml
    assert "infoEntityIdent" not in xml or "ICN-TODO" in xml  # graphics: infoEntityIdent only


def test_output_is_wellformed() -> None:
    etree.fromstring(_doc().encode("utf-8"))  # ne leve pas


def test_table_header_becomes_thead_and_colspec() -> None:
    root = IRNode(id="r", kind="section", level=0)
    root.children = [IRNode(
        id="t", kind="table", form="table",
        table_rows=[["Bolt", "Torque"], ["M6", "12"]],
        table_header=["Bolt", "Torque"],
    )]
    resolve(root)
    xml = serialize(root, issue="5.0", dm_type="descriptive")
    doc = etree.fromstring(xml.encode("utf-8"))
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
    doc = etree.fromstring(xml.encode("utf-8"))
    ref = doc.find(".//internalRef")
    assert ref is not None
    assert ref.get("internalRefTargetType") == "figure"
