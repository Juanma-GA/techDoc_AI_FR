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
        blocks.append(
            RawBlock(
                text=text,
                page=page_idx,
                font_size=round(max_size, 1) or None,
                bold=_block_is_bold(spans_all),
            )
        )
    return blocks


def parse_pdf_pages(path: str | Path) -> list[PageParse]:
    """Parse le PDF page par page ; chaque page sait si elle a une couche texte."""
    doc = fitz.open(str(path))
    try:
        out: list[PageParse] = []
        for idx, page in enumerate(doc, start=1):
            raw_text = page.get_text("text") or ""
            has_text = len(raw_text.strip()) >= _MIN_TEXT_CHARS
            blocks = _page_blocks(page, idx) if has_text else []
            out.append(PageParse(index=idx, blocks=blocks, has_text=has_text))
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
