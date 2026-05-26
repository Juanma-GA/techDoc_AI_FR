"""Parseur DOCX via python-docx (paragraphes + tables)."""

from __future__ import annotations

from docx import Document  # type: ignore[import-untyped]


def parse(path: str) -> dict[str, str]:
    doc = Document(path)
    parts: list[str] = []

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            row_text = " | ".join(c for c in cells if c)
            if row_text:
                parts.append(row_text)

    return {"text": "\n".join(parts)}
