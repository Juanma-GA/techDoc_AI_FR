"""Parsing .docx pour le reviewer (pendant docx de `pdf_parser`).

`parse_docx(path)` retourne un `ParsedDocx` oriente **blocs** (paragraphes /
cellules de tableau / en-tetes / pieds), chacun portant un `target_id` stable
`dp<N>` (ordre de parcours deterministe, identique a celui qu'utilisera
l'editeur pour reappliquer un patch). Pas de geometrie (bbox/pages) : Word a une
mise en page en flux, pas de coordonnees absolues.

Specifique CMM : on lit aussi le **suivi de modifications** Word
(`w:ins`/`w:del`/`w:pPrChange`/`w:rPrChange`) et les **barres de revision**
(`w:pBdr`) pour savoir quels blocs sont modifies — base des `revision_check`.

La reconnaissance des **zones semantiques** (footer, fiche_suiveuse,
highlights_table...) est faite a part par `app.core.docx_zones.recognize_zones`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from docx import Document  # type: ignore[import-untyped]
from docx.enum.text import WD_ALIGN_PARAGRAPH  # type: ignore[import-untyped]
from docx.table import Table, _Cell  # type: ignore[import-untyped]
from docx.text.paragraph import Paragraph  # type: ignore[import-untyped]


_ALIGN_MAP = {
    WD_ALIGN_PARAGRAPH.LEFT: "left",
    WD_ALIGN_PARAGRAPH.CENTER: "center",
    WD_ALIGN_PARAGRAPH.RIGHT: "right",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
}


@dataclass
class Block:
    target_id: str  # "dp<N>" stable, partage avec l'editeur
    index: int  # 1-indexed (ordre de parcours)
    zone: str  # "body" | "header" | "footer"
    kind: str  # "paragraph" | "cell" | "heading"
    text: str
    style_name: str = ""
    alignment: Optional[str] = None  # left | center | right | justify | None
    heading_level: Optional[int] = None
    revised: bool = False
    revision_kind: Optional[str] = None  # ins | del | fmt | bar | None
    table_label: str = ""  # contexte ligne/colonne pour une cellule
    table_id: Optional[int] = None  # id du tableau (pour reconstruire la vue)
    row: Optional[int] = None  # index de ligne dans le tableau
    col: Optional[int] = None  # index de colonne logique
    semantic_zone: Optional[str] = None  # rempli par docx_zones
    page: int = 1  # numero de page (corps) deduit des sauts de page Word


@dataclass
class Revision:
    target_id: str
    kind: str
    author: str = ""
    date: str = ""


@dataclass
class ParsedDocx:
    block_count: int
    blocks: list[Block]
    headers: list[str]
    footers: list[str]
    full_text: str
    revisions: list[Revision] = field(default_factory=list)
    zones: dict[str, list[Block]] = field(default_factory=dict)
    meta: dict[str, object] = field(default_factory=dict)

    def block_by_target(self, target_id: str) -> Optional[Block]:
        for b in self.blocks:
            if b.target_id == target_id:
                return b
        return None


def _para_text(paragraph: Paragraph) -> str:
    return "".join(run.text for run in paragraph.runs)


def _style_name(paragraph: Paragraph) -> str:
    try:
        return str(paragraph.style.name) if paragraph.style is not None else ""
    except (AttributeError, ValueError):
        return ""


def _alignment(paragraph: Paragraph) -> Optional[str]:
    try:
        return _ALIGN_MAP.get(paragraph.alignment)
    except (AttributeError, ValueError):
        return None


def _heading_level(style_name: str) -> Optional[int]:
    if style_name.startswith("Heading "):
        tail = style_name.removeprefix("Heading ").strip()
        if tail.isdigit():
            return int(tail)
    if style_name in {"Title", "Titre"}:
        return 0
    return None


def _xpath(elem: object, expr: str) -> list:
    """xpath sur un element OXML python-docx (le prefixe `w:` est connu)."""
    try:
        return list(elem.xpath(expr))  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return []


def _has_page_break(paragraph: Paragraph) -> bool:
    """Le paragraphe contient-il un saut de page (rendu par Word ou manuel) ?"""
    p = paragraph._p  # noqa: SLF001 — acces a l'OXML, intentionnel
    if _xpath(p, ".//w:lastRenderedPageBreak"):
        return True
    return bool(_xpath(p, './/w:br[@w:type="page"]'))


def _revision_info(paragraph: Paragraph) -> tuple[Optional[str], str, str]:
    """(revision_kind, author, date) du paragraphe via le track-changes Word."""
    p = paragraph._p  # noqa: SLF001 — acces a l'OXML, intentionnel
    for tag, kind in (("w:ins", "ins"), ("w:del", "del")):
        nodes = _xpath(p, f".//{tag}")
        if nodes:
            node = nodes[0]
            author = node.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author", ""
            )
            date = node.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}date", ""
            )
            return kind, author or "", date or ""
    if _xpath(p, ".//w:pPrChange") or _xpath(p, ".//w:rPrChange"):
        return "fmt", "", ""
    if _xpath(p, "./w:pPr/w:pBdr"):
        return "bar", "", ""
    return None, "", ""


def _is_vmerge_continuation(tc: object) -> bool:
    """Continuation d'une fusion verticale (vMerge sans val='restart')."""
    vmerge = _xpath(tc, "./w:tcPr/w:vMerge")
    if not vmerge:
        return False
    val = vmerge[0].get(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
    )
    return val != "restart"


def _inner_blocks(container: object) -> list:
    try:
        return list(container.iter_inner_content())  # type: ignore[attr-defined]
    except AttributeError:
        blocks: list = list(getattr(container, "paragraphs", []))
        blocks.extend(getattr(container, "tables", []))
        return blocks


def _cell_text(cell: _Cell) -> str:
    try:
        return (cell.text or "").strip()
    except (AttributeError, ValueError):
        return ""


def iter_doc_paragraphs(doc: object) -> Iterator[tuple[int, str, str, dict, Paragraph]]:
    """Walker deterministe **partage** entre le parser et l'editeur.

    Yield `(index, zone, kind_hint, ctx, paragraph)` dans l'ordre : corps (tables
    entrelacees, cellules physiques, vMerge ignore) puis en-tetes / pieds non lies.
    `ctx` = {table_label, table_id, row, col} (vide hors tableau). Garantit que
    `dp<N>` designe le meme paragraphe a l'analyse et a l'edition.
    """
    counter = 0
    table_seq = 0

    def walk_table(table: Table, zone: str) -> Iterator[tuple[int, str, str, dict, Paragraph]]:
        nonlocal counter, table_seq
        table_seq += 1
        table_id = table_seq
        tr_list = list(table._tbl.tr_lst)  # noqa: SLF001
        header_cells: list[str] = []
        if tr_list:
            header_cells = [_cell_text(_Cell(tc, table)) for tc in tr_list[0].tc_lst]
        for r_idx, tr in enumerate(tr_list):
            tcs = list(tr.tc_lst)
            first_cell_text = _cell_text(_Cell(tcs[0], table)) if tcs else ""
            col = 0
            for tc in tcs:
                span = tc.grid_span or 1
                if _is_vmerge_continuation(tc):
                    col += span
                    continue
                cell = _Cell(tc, table)
                col_header = header_cells[col] if col < len(header_cells) and r_idx > 0 else ""
                own = _cell_text(cell)
                parts = [p for p in (first_cell_text, col_header) if p and p != own]
                ctx = {"table_label": " / ".join(parts), "table_id": table_id, "row": r_idx, "col": col}
                for inner in _inner_blocks(cell):
                    if isinstance(inner, Paragraph):
                        counter += 1
                        yield counter, zone, "cell", ctx, inner
                    elif isinstance(inner, Table):
                        yield from walk_table(inner, zone)
                col += span

    def walk_container(container: object, zone: str) -> Iterator[tuple[int, str, str, dict, Paragraph]]:
        nonlocal counter
        for inner in _inner_blocks(container):
            if isinstance(inner, Paragraph):
                counter += 1
                yield counter, zone, "paragraph", {}, inner
            elif isinstance(inner, Table):
                yield from walk_table(inner, zone)

    yield from walk_container(doc, "body")
    for section in doc.sections:
        header = section.header
        if not getattr(header, "is_linked_to_previous", False):
            yield from walk_container(header, "header")
        footer = section.footer
        if not getattr(footer, "is_linked_to_previous", False):
            yield from walk_container(footer, "footer")


def _make_block(index: int, zone: str, kind_hint: str, ctx: dict, paragraph: Paragraph) -> tuple[Block, Optional[Revision]]:
    text = _para_text(paragraph)
    style = _style_name(paragraph)
    level = _heading_level(style)
    kind = "heading" if (level is not None and kind_hint == "paragraph") else kind_hint
    rev_kind, author, date = _revision_info(paragraph)
    block = Block(
        target_id=f"dp{index}",
        index=index,
        zone=zone,
        kind=kind,
        text=text,
        style_name=style,
        alignment=_alignment(paragraph),
        heading_level=level,
        revised=rev_kind is not None,
        revision_kind=rev_kind,
        table_label=str(ctx.get("table_label", "")),
        table_id=ctx.get("table_id"),
        row=ctx.get("row"),
        col=ctx.get("col"),
    )
    rev = Revision(target_id=block.target_id, kind=rev_kind, author=author, date=date) if rev_kind else None
    return block, rev


def parse_docx(
    path: str | Path,
    *,
    progress_cb: Callable[[int, int | None], None] | None = None,
) -> ParsedDocx:
    doc = Document(str(path))
    blocks: list[Block] = []
    revisions: list[Revision] = []
    header_parts: list[str] = []
    footer_parts: list[str] = []

    page = 1
    page_has_content = False
    for index, zone, kind_hint, ctx, paragraph in iter_doc_paragraphs(doc):
        block, rev = _make_block(index, zone, kind_hint, ctx, paragraph)
        if zone == "body":
            # Un saut de page bascule ce bloc (et les suivants) sur la page d'apres.
            if page_has_content and _has_page_break(paragraph):
                page += 1
            block.page = page
            page_has_content = True
        blocks.append(block)
        if progress_cb is not None and len(blocks) % 25 == 0:
            progress_cb(len(blocks), None)
        if rev is not None:
            revisions.append(rev)
        if zone == "header" and block.text.strip():
            header_parts.append(block.text)
        elif zone == "footer" and block.text.strip():
            footer_parts.append(block.text)

    if progress_cb is not None and blocks and len(blocks) % 25:
        progress_cb(len(blocks), None)

    full_text = "\n".join(f"[BLOCK: {b.target_id}]\n{b.text}" for b in blocks)

    return ParsedDocx(
        block_count=len(blocks),
        blocks=blocks,
        headers=["\n".join(header_parts)] if header_parts else [],
        footers=["\n".join(footer_parts)] if footer_parts else [],
        full_text=full_text,
        revisions=revisions,
        meta={"revised_count": len(revisions)},
    )
