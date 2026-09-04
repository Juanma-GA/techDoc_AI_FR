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

import re

from lxml import etree

from app.core.ir import IRNode

_BANNER = (
    " Squelette structurel best-effort genere par s1000d extractor. "
    "NON valide comme Data Module : DMC / SNS / applicabilite / securite / ICN "
    "a completer manuellement (voir les commentaires TODO). "
)

# Caracteres de controle interdits en XML 1.0 (le texte d'un PDF en contient
# souvent : form feed, NUL...). lxml leve une ValueError -> 500 cote API. On les
# retire au seuil de la serialisation, une fois pour toutes.
_INVALID_XML_CHARS = re.compile(r"[^\u0009\u000A\u000D\u0020-\uD7FF\uE000-\uFFFD]")
# Nom d'element XML valide (les candidats viennent d'un override humain / LLM).
_NCNAME = re.compile(r"^[A-Za-z_][\w.\-]*$")


def xml_text(value: str | None) -> str:
    """Texte utilisable comme contenu XML (caracteres de controle retires)."""
    return _INVALID_XML_CHARS.sub("", value or "")


def _safe_element(name: str, fallback: str) -> str:
    return name if _NCNAME.match(name or "") else fallback


def _top_element(node: IRNode, fallback: str) -> str:
    element = node.candidates[0].element if node.candidates else fallback
    return _safe_element(element, fallback)


def _alt_comment(node: IRNode) -> str | None:
    if len(node.candidates) > 1:
        alts = ", ".join(f"{c.element}({c.score:.2f})" for c in node.candidates[1:])
        return f" alt: {alts} "
    return None


def _comment(text: str) -> etree._Comment:
    """Commentaire XML sur : pas de `--` (interdit) ni de caractere de controle."""
    return etree.Comment(xml_text(text).replace("--", "- -"))


def _emit_refs(parent: etree._Element, node: IRNode) -> None:
    """Emet les renvois detectes (best-effort) : `internalRef` pour un renvoi
    interne (figure/table/section), `externalPubRef` sinon, commentaire pour une
    URL. La cible S1000D (DMC/xref) reste a completer (marquee TODO)."""
    for ref in node.refs or []:
        kind = ref.get("kind")
        if kind == "internal":
            el = etree.SubElement(
                parent, "internalRef",
                internalRefTargetType=xml_text(ref.get("target_kind", "section")),
            )
            el.set("internalRefId", f"TODO-{xml_text(ref.get('target', ''))}")
            el.append(_comment(f" renvoi detecte : {ref.get('text', '')} "))
        elif kind == "uri":
            parent.append(_comment(f" lien externe (a mapper) : {ref.get('target', '')} "))
        else:
            etree.SubElement(parent, "externalPubRef").append(
                _comment(f" TODO: publication externe : {ref.get('text', '')} ")
            )


def _para(parent: etree._Element, text: str) -> None:
    el = etree.SubElement(parent, "para")
    el.text = xml_text(text)


def _emit_row(parent: etree._Element, cells: list[str]) -> None:
    row_el = etree.SubElement(parent, "row")
    for cell in cells:
        entry = etree.SubElement(row_el, "entry")
        _para(entry, cell)


def _emit_table(parent: etree._Element, node: IRNode) -> None:
    """Modele CALS S1000D : table > (title?) > tgroup > colspec* > thead? > tbody.

    Une ligne d'entete detectee (`table_header`) devient un vrai `<thead>` ; les
    colonnes sont declarees en `<colspec>` (structure attendue par les outils
    S1000D), le reste va dans `<tbody>`."""
    rows = node.table_rows or []
    header = node.table_header
    body_rows = rows
    if header and rows and rows[0] == header:
        body_rows = rows[1:]          # evite de repeter l'entete dans le corps
    ncols = max([len(r) for r in rows] + ([len(header)] if header else []), default=1)
    table = etree.SubElement(parent, "table")
    if node.text:
        etree.SubElement(table, "title").text = xml_text(node.text)
    tgroup = etree.SubElement(table, "tgroup", cols=str(ncols))
    for c in range(1, ncols + 1):
        etree.SubElement(tgroup, "colspec", colname=f"c{c}")
    if header:
        thead = etree.SubElement(tgroup, "thead")
        _emit_row(thead, header)
    tbody = etree.SubElement(tgroup, "tbody")
    for row in body_rows:
        _emit_row(tbody, row)


def _emit_figure(parent: etree._Element, node: IRNode) -> None:
    fig = etree.SubElement(parent, "figure")
    title = etree.SubElement(fig, "title")
    title.text = xml_text(node.text) or "Figure"
    if node.icn:
        # ICN reelle : illustration extraite et enregistree (nom de fichier).
        etree.SubElement(fig, "graphic", infoEntityIdent=xml_text(node.icn))
    else:
        fig.append(etree.Comment(" TODO: ICN du graphic a referencer (infoEntityIdent) "))
        etree.SubElement(fig, "graphic", infoEntityIdent="ICN-TODO-00000")


def _emit_admonition(parent: etree._Element, node: IRNode) -> None:
    # Fallback si la resolution n'a pas tourne (candidats vides) : sans lui,
    # l'acces `candidates[0]` levait une IndexError -> 500 "Unexpected server error".
    element = _top_element(node, node.admonition or "note")
    el = etree.SubElement(parent, element)
    child = "notePara" if node.admonition == "note" else "warningAndCautionPara"
    para = etree.SubElement(el, child)
    para.text = xml_text(node.text)


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
        _emit_refs(li, item)


def _emit_node(parent: etree._Element, node: IRNode) -> None:
    alt = _alt_comment(node)
    if alt:
        parent.append(etree.Comment(alt))

    if node.kind == "admonition":
        _emit_admonition(parent, node)
        _emit_refs(parent, node)
    elif node.kind == "figure":
        _emit_figure(parent, node)
        _emit_refs(parent, node)
    elif node.kind == "table":
        _emit_table(parent, node)
    elif node.kind == "item-sequence":
        _emit_list(parent, node)
    elif node.kind == "paragraph":
        top = _top_element(node, "para")
        if top == "proceduralStep":
            step = etree.SubElement(parent, "proceduralStep")
            _para(step, node.text)
            _emit_refs(step, node)
        else:
            _para(parent, node.text)
            _emit_refs(parent, node)
    elif node.kind == "section":
        top = _top_element(node, "levelledPara")
        sect = etree.SubElement(parent, top)
        if node.text:
            title = etree.SubElement(sect, "title")  # optionnel mais conventionnel
            title.text = xml_text(node.text)
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
        ident.append(etree.Comment(f" dmTitle (detecte) : {xml_text(title).replace('--', '- -')} "))
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
