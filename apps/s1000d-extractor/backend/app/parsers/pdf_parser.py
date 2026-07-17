"""Adapter PDF -> blocs bruts (PyMuPDF), avec detection par page.

Couverture de TOUS les PDF :
- page avec couche texte exploitable  -> lecture directe (spans + police) ;
- page sans texte (scannee / image)   -> signalee `has_text=False` pour que la
  couche superieure (`core.ingest`) la confie a l'OCR Mistral.

La decision est PAR PAGE : un PDF mixte (pages texte + pages scannees) est donc
correctement couvert, sans perdre les pages scannees ni re-OCR les pages texte.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

from app.core.ir import RawBlock

# Bit 2^4 (=16) du flag span PyMuPDF = gras ; on detecte aussi via le nom.
_BOLD_FLAG = 1 << 4
# En-dessous de ce nombre de caracteres, on considere la page non lisible
# (scannee) et on la bascule vers l'OCR.
_MIN_TEXT_CHARS = 16


@dataclass
class PageParse:
    index: int                                   # 1-indexe
    blocks: list[RawBlock] = field(default_factory=list)
    has_text: bool = False


def _block_is_bold(spans: list[dict]) -> bool:
    for s in spans:
        if int(s.get("flags", 0)) & _BOLD_FLAG:
            return True
        if "bold" in str(s.get("font", "")).lower():
            return True
    return False


def _page_blocks(page: fitz.Page, page_idx: int) -> list[RawBlock]:
    data = page.get_text("dict")
    blocks: list[RawBlock] = []
    # Bbox PyMuPDF : origine coin HAUT-gauche, y croissant vers le BAS => un entete
    # a un petit y0, un pied de page un grand y1. Pour une page tournee, ce mapping
    # est faux -> on neutralise la geometrie (page_height=None) et zone reste body.
    rotated = int(page.rotation) != 0
    page_height = None if rotated else round(float(page.rect.height), 1)
    for block in data.get("blocks", []):
        lines = block.get("lines", [])
        if not lines:
            continue
        parts: list[str] = []
        spans_all: list[dict] = []
        max_size = 0.0
        for line in lines:
            line_spans = line.get("spans", [])
            spans_all.extend(line_spans)
            line_text = "".join(s.get("text", "") for s in line_spans)
            if line_text.strip():
                parts.append(line_text)
            for s in line_spans:
                max_size = max(max_size, float(s.get("size", 0.0)))
        text = "\n".join(parts).strip()
        if not text:
            continue
        bbox = block.get("bbox") or (None, None, None, None)
        blocks.append(
            RawBlock(
                text=text,
                page=page_idx,
                font_size=round(max_size, 1) or None,
                bold=_block_is_bold(spans_all),
                y0=None if rotated or bbox[1] is None else round(float(bbox[1]), 1),
                y1=None if rotated or bbox[3] is None else round(float(bbox[3]), 1),
                page_height=page_height,
            )
        )
    return blocks


def _in_vertical_band(y0: float, y1: float, band: tuple, *, pad: float = 3.0) -> bool:
    """Vrai si [y0,y1] est dans la bande verticale d'un tableau (by0..by1).

    La RawBlock ne porte pas d'abscisse : on se fie a la bande verticale (un
    tableau occupe sa propre tranche de page), suffisant pour l'anti-doublon."""
    return y0 >= band[1] - pad and y1 <= band[3] + pad


def _table_blocks(
    page: fitz.Page, page_idx: int, page_height: float | None
) -> tuple[list[RawBlock], list[tuple]]:
    """Detecte les tableaux (PyMuPDF `find_tables`) -> RawBlock CALS + bboxes.

    Renvoie (blocs table, bboxes) ; les bboxes servent a exclure le texte interne
    (anti-doublon) cote appelant. Best-effort : si l'API n'existe pas ou echoue,
    renvoie ([], [])."""
    blocks: list[RawBlock] = []
    bboxes: list[tuple] = []
    try:
        found = page.find_tables()
    except Exception:
        return blocks, bboxes
    for tbl in getattr(found, "tables", []) or []:
        try:
            rows = [[(c or "").strip() for c in row] for row in tbl.extract()]
        except Exception:
            continue
        rows = [r for r in rows if any(r)]
        if not rows:
            continue
        header = None
        names = [n for n in (getattr(getattr(tbl, "header", None), "names", None) or []) if n]
        if names:
            header = [str(n).strip() for n in names]
        bbox = tuple(float(v) for v in tbl.bbox)
        blocks.append(RawBlock(
            text=" ".join(c for r in rows for c in r),
            page=page_idx, is_table=True, table_rows=rows, table_header=header,
            y0=round(bbox[1], 1), y1=round(bbox[3], 1), page_height=page_height,
        ))
        bboxes.append(bbox)
    return blocks, bboxes


def parse_pdf_pages(path: str | Path) -> list[PageParse]:
    """Parse le PDF page par page ; chaque page sait si elle a une couche texte.

    Detecte aussi les tableaux (modele CALS) et exclut le texte qui tombe dans un
    tableau pour ne pas le dupliquer en paragraphes."""
    doc = fitz.open(str(path))
    try:
        out: list[PageParse] = []
        for idx, page in enumerate(doc, start=1):
            raw_text = page.get_text("text") or ""
            has_text = len(raw_text.strip()) >= _MIN_TEXT_CHARS
            if not has_text:
                out.append(PageParse(index=idx, blocks=[], has_text=False))
                continue
            page_height = None if int(page.rotation) != 0 else round(float(page.rect.height), 1)
            tbl_blocks, tbl_bboxes = _table_blocks(page, idx, page_height)
            text_blocks = _page_blocks(page, idx)
            if tbl_bboxes:
                text_blocks = [
                    b for b in text_blocks
                    if b.y0 is None or b.y1 is None
                    or not any(_in_vertical_band(b.y0, b.y1, bx) for bx in tbl_bboxes)
                ]
            merged = sorted(text_blocks + tbl_blocks, key=lambda b: (b.y0 if b.y0 is not None else 0.0))
            out.append(PageParse(index=idx, blocks=merged, has_text=True))
        return out
    finally:
        doc.close()


def parse_pdf(path: str | Path) -> list[RawBlock]:
    """Compat : blocs texte aplatis. Leve `PDF_NO_TEXT_LAYER` si aucune page
    n'a de couche texte (le repli OCR est gere par `core.ingest`)."""
    from app.core.errors import AppError

    pages = parse_pdf_pages(path)
    blocks = [b for p in pages for b in p.blocks]
    if not any(p.has_text for p in pages):
        raise AppError(
            "PDF_NO_TEXT_LAYER",
            "Ce PDF n'a pas de couche texte extractible (scanne ?).",
            status_code=422,
        )
    return blocks


def pdf_page_count(path: str | Path) -> int:
    doc = fitz.open(str(path))
    try:
        return int(doc.page_count)
    finally:
        doc.close()
