"""Parseur PDF via PyMuPDF (fitz)."""

from __future__ import annotations

import fitz  # type: ignore[import-untyped]


def parse(path: str) -> dict[str, str]:
    parts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text("text") or ""
            if text.strip():
                parts.append(text)
    return {"text": "\n\n".join(parts)}
