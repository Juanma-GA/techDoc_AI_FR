"""Cheap, text-only detection of the norm a PDF follows (no layout parsing)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import fitz

from app.checks.client_bundle import ClientBundle
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


def read_page_texts(path: str | Path, limit: int | None = None) -> list[str]:
    pdf = fitz.open(str(path))
    try:
        count = pdf.page_count if limit is None else min(pdf.page_count, limit)
        return [pdf.load_page(index).get_text("text") or "" for index in range(count)]
    finally:
        pdf.close()


def text_only_pdf(texts: Sequence[str]) -> ParsedPdf:
    pages = [ParsedPage(page=index, text=text) for index, text in enumerate(texts, start=1)]
    return ParsedPdf(
        page_count=len(pages),
        pages=pages,
        full_text="\n".join(texts),
        is_signed=False,
    )


def detect_document_norm(bundle: ClientBundle[Any], texts: Sequence[str]) -> str | None:
    """Code of the norm that claims the PDF, `default_norm` when none does, None without norms."""
    if bundle.norm_selector is None:
        return bundle.default_norm
    return bundle.norm_selector(text_only_pdf(texts))
