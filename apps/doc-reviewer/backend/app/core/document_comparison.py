"""Extract PDF text-layer lines and page geometry for comparison."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.core.errors import AppError


@dataclass(frozen=True)
class PdfTextLine:
    text: str
    normalized: str
    page: int
    bbox: tuple[float, float, float, float]
    page_width: float
    page_height: float
    page_rotation: int


@dataclass(frozen=True)
class PdfTextPage:
    page: int
    text: str


@dataclass(frozen=True)
class ExtractedPdf:
    page_count: int
    lines: tuple[PdfTextLine, ...]
    pages: tuple[PdfTextPage, ...]


def extract_pdf_text(path: Path) -> ExtractedPdf:
    try:
        document = fitz.open(str(path))
    except (fitz.FileDataError, RuntimeError) as exc:
        raise AppError("PDF_INVALID", "Le PDF est illisible.", status_code=400) from exc

    try:
        lines: list[PdfTextLine] = []
        pages: list[PdfTextPage] = []
        for page_number, page in enumerate(document, start=1):
            page_width = float(page.rect.width)
            page_height = float(page.rect.height)
            page_rotation = int(page.rotation)
            normalized_lines: list[str] = []
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    text = "".join(span.get("text", "") or "" for span in line.get("spans", []))
                    normalized = re.sub(r"\s+", " ", text).strip()
                    if not normalized:
                        continue
                    raw_bbox = line.get("bbox", (0.0, 0.0, 0.0, 0.0))
                    bbox = tuple(float(value) for value in raw_bbox)
                    normalized_lines.append(normalized)
                    lines.append(
                        PdfTextLine(
                            text=text.strip(),
                            normalized=normalized,
                            page=page_number,
                            bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
                            page_width=page_width,
                            page_height=page_height,
                            page_rotation=page_rotation,
                        )
                    )
            page_text = re.sub(r"\s+", " ", page.get_text("text") or "").strip()
            pages.append(
                PdfTextPage(
                    page=page_number,
                    text=page_text or " ".join(normalized_lines),
                )
            )

        if not lines:
            raise AppError(
                "PDF_NO_TEXT_LAYER",
                "Aucun texte exploitable n'a été trouvé dans ce PDF. L'OCR n'est pas utilisé.",
                status_code=422,
            )
        return ExtractedPdf(
            page_count=document.page_count,
            lines=tuple(lines),
            pages=tuple(pages),
        )
    finally:
        document.close()
