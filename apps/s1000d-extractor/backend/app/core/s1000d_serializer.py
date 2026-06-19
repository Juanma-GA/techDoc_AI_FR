"""Serialiseur : IR resolu -> squelette XML S1000D (lxml).

ATTENTION (ecart assume) : la sortie est un SQUELETTE STRUCTUREL best-effort,
PAS un Data Module valide. Les metadonnees non recuperables d'un PDF/Word
(DMC, SNS, applicabilite, securite, ICN des graphics) sont des placeholders
marques `<!-- TODO ... -->` a completer par un humain.

Noms d'elements conformes Issue 4.2 / 5.0 (stables entre les deux) :
- bloc d'identification : `identAndStatusSection` (`dmAddress` + `dmStatus`,
  le `brexDmRef` vit dans `dmStatus`) ;
- listes : `randomList`/`sequentialList` > `listItem` > `para` ;
- procedure : `procedure` > `mainProcedure` > `proceduralStep` > `para` ;
- admonitions : `warning`/`caution` > `warningAndCautionPara`, `note` > `notePara` ;
- figure : `figure` > `title` + `graphic[@infoEntityIdent]` (PAS `boardno`, legacy 2.x) ;
- tableaux : modele CALS `table` > `tgroup` > `tbody` > `row` > `entry` > `para`.
"""

from __future__ import annotations

from lxml import etree

from app.core.ir import IRNode

_BANNER = (
    " Squelette structurel best-effort genere par s1000d extractor. "
    "NON valide comme Data Module : DMC / SNS / applicabilite / securite / ICN "
    "a completer manuellement (voir les commentaires TODO). "
)


def _top_element(node: IRNode, fallback: str) -> str:
    return node.candidates[0].element if node.candidates else fallback


def _alt_comment(node: IRNode) -> str | None:
    if len(node.candidates) > 1:
        alts = ", ".join(f"{c.element}({c.score:.2f})" for c in node.candidates[1:])
        return f" alt: {alts} "
    return None


def _para(parent: etree._Element, text: str) -> None:
    el = etree.SubElement(parent, "para")
    el.text = text or ""


def _emit_table(parent: etree._Element, node: IRNode) -> None:
    rows = node.table_rows or []
    ncols = max((len(r) for r in rows), default=1)
    table = etree.SubElement(parent, "table")
    tgroup = etree.SubElement(table, "tgroup", cols=str(ncols))
    tbody = etree.SubElement(tgroup, "tbody")
    for row in rows:
        row_el = etree.SubElement(tbody, "row")
        for cell in row:
            entry = etree.SubElement(row_el, "entry")
            _para(entry, cell)


def _emit_figure(parent: etree._Element, node: IRNode) -> None:
    fig = etree.SubElement(parent, "figure")
    title = etree.SubElement(fig, "title")
    title.text = node.text or "Figure"
    fig.append(etree.Comment(" TODO: ICN du graphic a referencer (infoEntityIdent) "))
    etree.SubElement(fig, "graphic", infoEntityIdent="ICN-TODO-00000")


def _emit_admonition(parent: etree._Element, node: IRNode) -> None:
    el = etree.SubElement(parent, node.candidates[0].element)
    child = "notePara" if node.admonition == "note" else "warningAndCautionPara"
    para = etree.SubElement(el, child)
    para.text = node.text or ""


def _emit_list(parent: etree._Element, node: IRNode) -> None:
    top = _top_element(node, "randomList")
    if top == "proceduralStep":
        # En procedure, chaque item devient une etape independante.
        for item in node.children:
            step = etree.SubElement(parent, "proceduralStep")
            _para(step, item.text)
        return
    list_el = etree.SubElement(parent, top)
    for item in node.children:
        li = etree.SubElement(list_el, "listItem")
        _para(li, item.text)


def _emit_node(parent: etree._Element, node: IRNode) -> None:
    alt = _alt_comment(node)
    if alt:
        parent.append(etree.Comment(alt))

    if node.kind == "admonition":
        _emit_admonition(parent, node)
    elif node.kind == "figure":
        _emit_figure(parent, node)
    elif node.kind == "table":
        _emit_table(parent, node)
    elif node.kind == "item-sequence":
        _emit_list(parent, node)
    elif node.kind == "paragraph":
        top = _top_element(node, "para")
        if top == "proceduralStep":
            step = etree.SubElement(parent, "proceduralStep")
            _para(step, node.text)
        else:
            _para(parent, node.text)
    elif node.kind == "section":
        top = _top_element(node, "levelledPara")
        sect = etree.SubElement(parent, top)
        if node.text:
            title = etree.SubElement(sect, "title")  # optionnel mais conventionnel
            title.text = node.text
        for child in node.children:
            _emit_node(sect, child)


def _build_content(root: IRNode, dm_type: str) -> etree._Element:
    content = etree.Element("content")
    if dm_type == "procedural":
        proc = etree.SubElement(content, "procedure")
        proc.append(etree.Comment(" TODO: preliminaryRqmts (outillage, consommables, conditions) "))
        etree.SubElement(proc, "preliminaryRqmts")
        main = etree.SubElement(proc, "mainProcedure")
        for child in root.children:
            _emit_node(main, child)
        etree.SubElement(proc, "closeRqmts")
    else:
        desc = etree.SubElement(content, "description")
        if dm_type == "ipd":
            desc.append(etree.Comment(
                " TODO: catalogue de pieces (IPD/IPC) - structurer en catalogSeqNumber/itemSeqNumber "
            ))
        for child in root.children:
            _emit_node(desc, child)
    return content


def serialize(root: IRNode, *, issue: str, dm_type: str, title: str = "") -> str:
    """Construit le squelette XML S1000D complet (string UTF-8 indentee)."""
    dmodule = etree.Element("dmodule")
    dmodule.addprevious(etree.Comment(_BANNER))
    dmodule.set("s1000dExtractorIssue", issue)

    ident = etree.SubElement(dmodule, "identAndStatusSection")
    if title:
        ident.append(etree.Comment(f" dmTitle (detecte) : {title.replace('--', '- -')} "))
    ident.append(etree.Comment(" TODO: dmAddress (DMC, langue, issueInfo, dmTitle) a completer "))
    etree.SubElement(ident, "dmAddress")
    status = etree.SubElement(ident, "dmStatus")
    status.append(etree.Comment(" TODO: brexDmRef vers le BREX projet + security + applic "))
    etree.SubElement(status, "brexDmRef")

    dmodule.append(_build_content(root, dm_type))

    tree = dmodule.getroottree()
    return etree.tostring(
        tree, pretty_print=True, xml_declaration=True, encoding="UTF-8"
    ).decode("utf-8")
