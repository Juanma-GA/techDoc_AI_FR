"""Ingestion robuste : document -> blocs IR, OCR si necessaire.

Couvre TOUS les PDF via une decision PAR PAGE :
- page avec couche texte -> lue directement (PyMuPDF, police conservee) ;
- page sans texte (scannee) -> OCR Mistral, markdown converti en blocs.

Un PDF mixte (pages texte + pages scannees) est donc entierement couvert : on
ne perd aucune page scannee et on ne re-OCR pas les pages texte. Un seul appel
OCR par document (Mistral OCR traite toutes les pages). Sans cle Mistral, les
pages scannees sont signalees : si TOUT est scanne -> erreur explicite, sinon on
poursuit avec les pages texte en signalant les pages ignorees.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

import pymupdf as fitz
from sqlalchemy.orm import Session

from app.core import ocr
from app.core.errors import AppError
from app.core.ir import RawBlock
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf_pages

log = logging.getLogger("s1000d_extractor.ingest")

ProgressCb = Callable[[str, int], None]


def extract_blocks(
    path: str | Path,
    *,
    fmt: str,
    db: Session | None = None,
    progress_cb: ProgressCb | None = None,
    local_only: bool = False,
) -> list[RawBlock]:
    if fmt == "docx":
        return parse_docx(path)
    if fmt != "pdf":
        raise AppError("UNSUPPORTED_FORMAT", f"Format non supporte : {fmt}", status_code=415)

    last_pct = 10

    def report_parse_progress(completed: int, total: int) -> None:
        nonlocal last_pct
        if progress_cb is None or total <= 0:
            return
        pct = 10 + (20 * completed) // total
        if pct > last_pct:
            last_pct = pct
            progress_cb("parse", pct)

    parse_started = perf_counter()
    pages = parse_pdf_pages(
        path,
        progress_cb=report_parse_progress if progress_cb is not None else None,
    )
    scanned = [p for p in pages if not p.has_text]
    log.info(
        "pdf_parse_timing duration_ms=%.1f page_count=%d text_page_count=%d "
        "scanned_page_count=%d block_count=%d",
        (perf_counter() - parse_started) * 1000,
        len(pages),
        len(pages) - len(scanned),
        len(scanned),
        sum(len(page.blocks) for page in pages),
    )
    if local_only:
        with fitz.open(str(path)) as source:
            requires_ocr = [
                page.index for page in scanned
                if source[page.index - 1].get_image_info()
                or (source[page.index - 1].get_drawings()
                    and not source[page.index - 1].get_text("text").strip())
            ]
        if requires_ocr:
            raise AppError(
                "LOCAL_OCR_REQUIRED",
                "Wizard local : certaines pages necessitent une couche texte. "
                "Fournissez un PDF avec OCR effectue localement ; aucun contenu n'a ete envoye.",
                status_code=422, detail={"pages_in_analyzed_pdf": requires_ocr},
            )
        blocks = [block for page in pages for block in page.blocks]
        if not any(block.text.strip() or block.table_rows for block in blocks):
            raise AppError("EMPTY_SOURCE", "Aucun texte exploitable dans la source locale.", 422)
        return blocks

    # Cas 1 : tout est lisible en texte -> aucun OCR.
    if not scanned:
        return [b for p in pages for b in p.blocks]

    # Cas 2 : au moins une page scannee, mais pas d'OCR disponible.
    if not ocr.ocr_available(db):
        text_blocks = [b for p in pages if p.has_text for b in p.blocks]
        if not text_blocks:
            raise AppError(
                "OCR_UNAVAILABLE",
                "PDF scanne : l'OCR necessite une cle Mistral (onglet Parametres).",
                status_code=422,
            )
        log.warning(
            "Pages scannees ignorees (pas de cle OCR) : %s",
            [p.index for p in scanned],
        )
        return text_blocks

    # Cas 3 : OCR des pages scannees, fusion avec les pages texte (ordre conserve).
    if progress_cb:
        progress_cb("ocr", 30)
    scanned_page_numbers = [p.index for p in scanned]
    ocr_started = perf_counter()
    pages_md = ocr.run_ocr(path, db, page_numbers=scanned_page_numbers)  # type: ignore[arg-type]
    log.info(
        "pdf_ocr_timing duration_ms=%.1f scanned_page_count=%d result_page_count=%d",
        (perf_counter() - ocr_started) * 1000,
        len(scanned_page_numbers),
        len(pages_md),
    )
    markdown_by_page = dict(zip(scanned_page_numbers, pages_md, strict=False))

    blocks: list[RawBlock] = []
    for p in pages:
        if p.has_text:
            blocks.extend(p.blocks)
        else:
            md = markdown_by_page.get(p.index, "")
            blocks.extend(ocr.markdown_to_blocks(md, page=p.index))

    if not blocks:
        raise AppError(
            "OCR_EMPTY",
            "Aucun texte exploitable n'a pu etre extrait de ce PDF (meme par OCR).",
            status_code=422,
        )
    return blocks
