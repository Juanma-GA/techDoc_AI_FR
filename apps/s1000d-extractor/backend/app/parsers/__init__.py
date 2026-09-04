"""Adapters d'entree : document source -> liste de `RawBlock` (IR brut).

PDF et DOCX se normalisent dans le MEME vocabulaire de blocs, ce qui permet a
tout le pipeline aval d'etre agnostique au format d'entree.
"""

from __future__ import annotations

from pathlib import Path

from app.core.errors import AppError
from app.core.ir import RawBlock
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf

SUPPORTED = {".pdf": "pdf", ".docx": "docx"}


def detect_format(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    fmt = SUPPORTED.get(ext)
    if fmt is None:
        raise AppError(
            "UNSUPPORTED_FORMAT",
            f"Format non supporte : {ext or '(aucun)'}. Attendu : PDF ou DOCX.",
            status_code=415,
        )
    return fmt


def parse_to_blocks(path: str | Path, fmt: str) -> list[RawBlock]:
    """Dispatch vers l'adapter du format et renvoie les blocs bruts."""
    if fmt == "pdf":
        return parse_pdf(path)
    if fmt == "docx":
        return parse_docx(path)
    raise AppError("UNSUPPORTED_FORMAT", f"Format inconnu : {fmt}", status_code=415)


__all__ = ["SUPPORTED", "detect_format", "parse_to_blocks"]
