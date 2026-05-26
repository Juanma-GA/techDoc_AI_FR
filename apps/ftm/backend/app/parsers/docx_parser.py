"""DOCX parser. Ported from legacy with minor type cleanups."""

from __future__ import annotations

import re
from typing import Any

from docx import Document


DMC_REGEX = re.compile(r"DMC[A-Z0-9\-]{3,}")


def parse_docx(path: str) -> dict[str, Any]:
    doc = Document(path)
    paragraphs: list[str] = []
    sections: list[str] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        paragraphs.append(text)
        style = (p.style.name or "").lower() if p.style else ""
        if "heading" in style or "titre" in style:
            sections.append(text)

    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))

    full_text = "\n".join(paragraphs)

    images: list[dict[str, Any]] = []
    rels = doc.part.rels
    last_text = ""
    for i, para in enumerate(doc.paragraphs):
        txt = para.text.strip()
        if txt:
            last_text = txt
        for run in para.runs:
            blip_elems = run.element.findall(
                ".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
            )
            for blip in blip_elems:
                rid = blip.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                )
                if rid and rid in rels:
                    img_part = rels[rid].target_part
                    images.append({
                        "bytes": img_part.blob,
                        "mime": img_part.content_type,
                        "caption": last_text,
                        "context": _grab_context(doc.paragraphs, i, window=2),
                    })

    dmc_codes = sorted(set(DMC_REGEX.findall(full_text)))

    return {
        "text": full_text,
        "images": images,
        "sections": sections,
        "dmc_codes": dmc_codes,
    }


def _grab_context(paragraphs: list, index: int, window: int = 2) -> str:
    start = max(0, index - window)
    end = min(len(paragraphs), index + window + 1)
    return " ".join(p.text.strip() for p in paragraphs[start:end] if p.text.strip())
