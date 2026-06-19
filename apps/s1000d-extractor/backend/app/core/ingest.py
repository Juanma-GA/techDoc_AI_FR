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
) -> list[RawBlock]:
    if fmt == "docx":
        return parse_docx(path)
    if fmt != "pdf":
        raise AppError("UNSUPPORTED_FORMAT", f"Format non supporte : {fmt}", status_code=415)

    pages = parse_pdf_pages(path)
    scanned = [p for p in pages if not p.has_text]

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
        progress_cb("ocr", 20)
    pages_md = ocr.run_ocr(path, db)  # type: ignore[arg-type]

    blocks: list[RawBlock] = []
    for p in pages:
        if p.has_text:
            blocks.extend(p.blocks)
        else:
            md = pages_md[p.index - 1] if 0 <= p.index - 1 < len(pages_md) else ""
            blocks.extend(ocr.markdown_to_blocks(md, page=p.index))

    if not blocks:
        raise AppError(
            "OCR_EMPTY",
            "Aucun texte exploitable n'a pu etre extrait de ce PDF (meme par OCR).",
            status_code=422,
        )
    return blocks
