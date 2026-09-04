"""Adapter DOCX -> blocs bruts (python-docx).

Word est structurellement *plus riche* que le PDF : les styles ("Heading 1",
"List Paragraph"), les definitions de numerotation (puce vs decimal) et les
vraies tables sont explicites. L'adapter les lit directement, donc peu
d'inference est necessaire (contrairement au PDF). On parcourt le corps dans
l'ordre du document pour ne pas perdre la position des tableaux.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.ir import RawBlock

_HEADING_RE = re.compile(r"^heading\s+(\d+)$", re.IGNORECASE)


def _heading_level(style_name: str) -> int | None:
    if not style_name:
        return None
    name = style_name.strip()
    if name.lower() == "title":
        return 1
    m = _HEADING_RE.match(name)
    return int(m.group(1)) if m else None


def _numbering_map(doc: Document) -> dict[tuple[str, str], str]:
    """(numId, ilvl) -> "bullet" | "ordered", lu depuis la numbering part.

    Best-effort : si la partie numerotation est absente ou illisible, on
    renvoie un dict vide et l'appelant retombe sur une detection par marqueur.
    """
    out: dict[tuple[str, str], str] = {}
    try:
        num_part = doc.part.numbering_part
        root = num_part.element
    except Exception:
        return out

    abstract_fmt: dict[str, dict[str, str]] = {}
    for an in root.findall(qn("w:abstractNum")):
        aid = an.get(qn("w:abstractNumId"))
        if aid is None:
            continue
        lvls: dict[str, str] = {}
        for lvl in an.findall(qn("w:lvl")):
            ilvl = lvl.get(qn("w:ilvl")) or "0"
            fmt_el = lvl.find(qn("w:numFmt"))
            fmt = fmt_el.get(qn("w:val")) if fmt_el is not None else "bullet"
            lvls[ilvl] = "bullet" if fmt == "bullet" else "ordered"
        abstract_fmt[aid] = lvls

    for num in root.findall(qn("w:num")):
        num_id = num.get(qn("w:numId"))
        ref = num.find(qn("w:abstractNumId"))
        aid = ref.get(qn("w:val")) if ref is not None else None
        if num_id is None or aid is None:
            continue
        for ilvl, kind in abstract_fmt.get(aid, {}).items():
            out[(num_id, ilvl)] = kind
    return out


def _para_list_kind(p: Paragraph, numbering: dict[tuple[str, str], str]) -> tuple[str | None, int]:
    """Renvoie (list_kind, list_level) si le paragraphe est un item de liste."""
    ppr = p._p.pPr
    if ppr is None:
        return None, 0
    numpr = ppr.find(qn("w:numPr"))
    if numpr is None:
        return None, 0
    ilvl_el = numpr.find(qn("w:ilvl"))
    numid_el = numpr.find(qn("w:numId"))
    ilvl = ilvl_el.get(qn("w:val")) if ilvl_el is not None else "0"
    num_id = numid_el.get(qn("w:val")) if numid_el is not None else None
    level = int(ilvl) if ilvl and ilvl.isdigit() else 0
    if num_id is not None:
        kind = numbering.get((num_id, ilvl)) or "bullet"
        return kind, level
    # numPr present mais non resolu : c'est une liste, type indetermine.
    return "bullet", level


def _style_list_kind(style_name: str) -> str | None:
    """Fallback : la numerotation peut venir du STYLE (ex. "List Bullet",
    "List Number") sans `numPr` direct sur le paragraphe."""
    name = (style_name or "").lower()
    if "list number" in name or ("list paragraph" in name and "number" in name):
        return "ordered"
    if "list bullet" in name or "list paragraph" in name:
        return "bullet"
    return None


def _table_to_block(tbl: Table) -> RawBlock:
    rows: list[list[str]] = []
    for row in tbl.rows:
        rows.append([cell.text.strip() for cell in row.cells])
    flat = " ".join(c for r in rows for c in r)
    return RawBlock(text=flat, is_table=True, table_rows=rows)


def parse_docx(path: str | Path) -> list[RawBlock]:
    doc = Document(str(path))
    numbering = _numbering_map(doc)
    blocks: list[RawBlock] = []

    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag
        if tag == qn("w:p"):
            p = Paragraph(child, doc)
            text = p.text.strip()
            if not text:
                continue
            style = p.style.name if p.style else ""
            level = _heading_level(style)
            list_kind, list_level = _para_list_kind(p, numbering)
            if list_kind is None and level is None:
                list_kind = _style_list_kind(style)  # type: ignore[assignment]
            blocks.append(
                RawBlock(
                    text=text,
                    style_name=style,
                    heading_level=level,
                    list_kind=list_kind,  # type: ignore[arg-type]
                    list_level=list_level,
                    bold=bool(p.runs and all(r.bold for r in p.runs if r.text.strip())),
                )
            )
        elif tag == qn("w:tbl"):
            tbl = Table(child, doc)
            blocks.append(_table_to_block(tbl))

    return blocks
