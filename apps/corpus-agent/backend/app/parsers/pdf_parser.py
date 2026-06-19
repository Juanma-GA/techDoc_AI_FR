"""PDF parser using PyMuPDF. Ported from legacy."""

from __future__ import annotations

import re
from typing import Any

import fitz  # PyMuPDF


DMC_REGEX = re.compile(r"DMC[A-Z0-9\-]{3,}")


def parse_pdf(path: str) -> dict[str, Any]:
    doc = fitz.open(path)
    texts: list[str] = []
    sections: list[str] = []
    images: list[dict[str, Any]] = []

    for page_index, page in enumerate(doc):
        text = page.get_text("text") or ""
        # Marqueur structuré exploité par les checks pour situer une anomalie.
        texts.append(f"[PAGE: {page_index + 1}]\n{text}")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and len(stripped) < 120 and stripped[0].isupper() and stripped == stripped.title():
                sections.append(stripped)

        for img in page.get_images(full=True):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:  # CMYK -> RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_bytes = pix.tobytes("png")
                caption = _closest_caption(text, page_index)
                images.append({
                    "bytes": img_bytes,
                    "mime": "image/png",
                    "caption": caption,
                    "context": f"Page {page_index + 1}",
                })
                pix = None
            except Exception:  # noqa: BLE001
                continue

    doc.close()
    full_text = "\n".join(texts)
    dmc_codes = sorted(set(DMC_REGEX.findall(full_text)))

    return {
        "text": full_text,
        "images": images,
        "sections": list(dict.fromkeys(sections)),
        "dmc_codes": dmc_codes,
    }


def _closest_caption(page_text: str, page_index: int) -> str:
    for line in page_text.splitlines():
        s = line.strip()
        if re.match(r"^(figure|fig\.?|illustration)\s*\d+", s, re.IGNORECASE):
            return s
    return f"Page {page_index + 1}"
