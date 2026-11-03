"""Ingestion locale : document -> blocs IR.

Couvre TOUS les PDF via une decision PAR PAGE :
- page avec couche texte -> lue directement (PyMuPDF, police conservee) ;
- page scannee sans couche texte -> erreur demandant un OCR local prealable.

Un PDF mixte n'est jamais traite partiellement : les pages scannees ne sont pas
ignorees et aucun contenu n'est transmis a un service externe.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter

import pymupdf as fitz
import structlog

from app.core.errors import AppError
from app.core.ir import RawBlock
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf_pages

log = structlog.get_logger("s1000d_extractor.ingest")

ProgressCb = Callable[[str, int], None]


def extract_blocks(
    path: str | Path,
    *,
    fmt: str,
    progress_cb: ProgressCb | None = None,
    table_bboxes_by_page: dict[int, list[tuple[float, float, float, float]]] | None = None,
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
    if table_bboxes_by_page is not None:
        table_bboxes_by_page.update({page.index: page.table_bboxes for page in pages})
    scanned = [p for p in pages if not p.has_text]
    log.info(
        "document_ingest_done",
        duration_ms=round((perf_counter() - parse_started) * 1000, 1),
        page_count=len(pages),
        text_page_count=len(pages) - len(scanned),
        scanned_page_count=len(scanned),
        block_count=sum(len(page.blocks) for page in pages),
    )
    if scanned:
        with fitz.open(str(path)) as source:
            requires_ocr = [
                page.index for page in scanned
                if source[page.index - 1].get_image_info()
                or (source[page.index - 1].get_drawings()
                    and not source[page.index - 1].get_text("text").strip())
            ]
        if requires_ocr:
            raise AppError(
                "OCR_UNAVAILABLE",
                "Ce PDF contient des pages scannees. Effectuez un OCR local avant "
                "de l'importer ; aucun contenu n'a ete transmis.",
                status_code=422,
                detail={"pages_in_analyzed_pdf": requires_ocr},
            )
    blocks = [block for page in pages for block in page.blocks]
    if not any(block.text.strip() or block.table_rows for block in blocks):
        raise AppError("EMPTY_SOURCE", "Aucun texte exploitable dans le PDF.", 422)
    return blocks
