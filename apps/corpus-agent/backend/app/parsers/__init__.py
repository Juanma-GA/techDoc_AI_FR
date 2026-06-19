"""Parsers dispatcher.

`parse_any(path)` returns a dict with keys: text, images, sections, dmc_codes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .doc_parser import parse_doc
from .docx_parser import parse_docx
from .pdf_parser import parse_pdf
from .s1000d_parser import parse_s1000d
from .xlsx_parser import parse_xlsx


def parse_any(path: str) -> dict[str, Any]:
    ext = Path(path).suffix.lower()
    if ext == ".docx":
        return parse_docx(path)
    if ext == ".doc":
        return parse_doc(path)
    if ext == ".pdf":
        return parse_pdf(path)
    if ext in (".xlsx", ".xlsm"):
        return parse_xlsx(path)
    if ext in (".xml", ".s1000d"):
        return parse_s1000d(path)
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        text = ""
    return {"text": text, "images": [], "sections": [], "dmc_codes": []}
