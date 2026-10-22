"""Repli OCR pour les PDF scannes (sans couche texte) via Mistral OCR.

Un PDF scanne n'a pas de texte extractible : on l'envoie a l'API OCR Mistral,
qui renvoie du markdown par page, puis on convertit ce markdown en `RawBlock`
(meme vocabulaire que les adapters PDF/DOCX). Le pipeline aval est inchange.

Limite : l'OCR perd la police/taille, donc l'inference de titre repose sur le
markdown (`#`, `##`) et les heuristiques de texte, pas sur la mise en forme.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ir import RawBlock
from app.core.mistral_client import (
    MistralClient,
    MistralError,
    get_effective_settings,
    get_llm_enabled,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_ORDERED_RE = re.compile(r"^\s*\d{1,3}[.)]\s+(.*)$")
_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")


def ocr_available(db: Session | None) -> bool:
    return (
        db is not None
        and get_llm_enabled(db)
        and bool(get_effective_settings(db).get("api_key"))
    )


def run_ocr(
    path: str | Path,
    db: Session,
    *,
    page_numbers: list[int] | None = None,
) -> list[str]:
    """OCR le PDF via Mistral et renvoie le markdown, une entree par page.

    `page_numbers` utilise des numeros de page 1-indexes pour limiter l'OCR.
    Leve `OCR_FAILED` si l'appel echoue (message explicite cote UI).
    """
    if page_numbers is not None and not page_numbers:
        return []
    try:
        client = MistralClient.from_db(db)
        if page_numbers is None:
            pdf_bytes = Path(path).read_bytes()
        else:
            import pymupdf as fitz

            source = fitz.open(str(path))
            selected = fitz.open()
            try:
                for page_number in page_numbers:
                    if not 1 <= page_number <= source.page_count:
                        raise ValueError(f"Numero de page invalide pour l'OCR : {page_number}")
                    selected.insert_pdf(source, from_page=page_number - 1, to_page=page_number - 1)
                pdf_bytes = selected.tobytes()
            finally:
                selected.close()
                source.close()
        return client.ocr_pdf(pdf_bytes)
    except MistralError as exc:
        raise AppError("OCR_FAILED", f"OCR Mistral indisponible : {exc}", status_code=502) from exc
    except Exception as exc:
        raise AppError("OCR_FAILED", f"OCR Mistral a echoue : {exc}", status_code=502) from exc


def markdown_to_blocks(md: str, *, page: int | None = None) -> list[RawBlock]:
    """Convertit du markdown (sortie OCR) en blocs IR bruts."""
    blocks: list[RawBlock] = []
    table_rows: list[list[str]] = []

    def flush_table() -> None:
        nonlocal table_rows
        if table_rows:
            flat = " ".join(c for r in table_rows for c in r)
            blocks.append(RawBlock(text=flat, page=page, is_table=True, table_rows=table_rows))
            table_rows = []

    for raw_line in md.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush_table()
            continue

        if _TABLE_SEP_RE.match(line) and "|" in line:
            continue  # ligne de separation d'en-tete markdown
        m_tbl = _TABLE_ROW_RE.match(line)
        if m_tbl:
            cells = [c.strip() for c in m_tbl.group(1).split("|")]
            table_rows.append(cells)
            continue
        flush_table()

        m_h = _HEADING_RE.match(line)
        if m_h:
            blocks.append(RawBlock(text=m_h.group(2).strip(), page=page,
                                   heading_level=len(m_h.group(1))))
            continue
        m_o = _ORDERED_RE.match(line)
        if m_o:
            blocks.append(RawBlock(text=m_o.group(1).strip(), page=page, list_kind="ordered"))
            continue
        m_b = _BULLET_RE.match(line)
        if m_b:
            blocks.append(RawBlock(text=m_b.group(1).strip(), page=page, list_kind="bullet"))
            continue
        blocks.append(RawBlock(text=line.strip(), page=page))

    flush_table()
    return blocks
