"""Parseur PPTX via python-pptx : texte des shapes + notes du presentateur.

Une slide produit un bloc :

    # Slide N
    <texte shapes>
    Notes : <notes du presentateur>

Le format binaire `.ppt` (Office 97-2003) n'est pas gere par python-pptx.
"""

from __future__ import annotations

from pptx import Presentation  # type: ignore[import-untyped]


def _shape_text(shape) -> str:  # type: ignore[no-untyped-def]
    parts: list[str] = []
    if shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            text = "".join(run.text for run in paragraph.runs).strip()
            if text:
                parts.append(text)
    if shape.has_table:
        for row in shape.table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            row_text = " | ".join(c for c in cells if c)
            if row_text:
                parts.append(row_text)
    return "\n".join(parts)


def parse(path: str) -> dict[str, str]:
    prs = Presentation(path)
    parts: list[str] = []
    for idx, slide in enumerate(prs.slides, start=1):
        parts.append(f"# Slide {idx}")
        for shape in slide.shapes:
            text = _shape_text(shape)
            if text:
                parts.append(text)
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"Notes : {notes}")
    return {"text": "\n".join(parts)}
