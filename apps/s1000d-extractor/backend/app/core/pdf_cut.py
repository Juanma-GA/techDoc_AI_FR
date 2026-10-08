"""Detection et decoupage du PDF avant le premier chapitre."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf as fitz
from sqlalchemy.orm import Session

from app.config import settings
from app.core.dmrl import normalize
from app.core.errors import AppError
from app.db.models import Document

_TOC_LINE = re.compile(r"(?:\.{2,}|·{2,}|-{2,})\s*\d+\s*$")
_CHAPTER = re.compile(r"^(?:chapter|chapitre)\s+1(?:\b|\s*[-:.])", re.IGNORECASE)


def _first_dm_title(doc: Document) -> str:
    if not doc.dmrl_json:
        return ""
    try:
        entries = json.loads(doc.dmrl_json)
    except (TypeError, ValueError):
        return ""
    return str(entries[0].get("title") or "") if entries else ""


def _page_text(page: fitz.Page) -> str:
    return (page.get_text("text") or "").strip()


def _score_page(text: str, title: str) -> tuple[float, list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized_title = normalize(title)
    normalized_lines = [normalize(line) for line in lines]
    reasons: list[str] = []
    score = 0.0

    if normalized_title:
        if normalized_title in normalized_lines:
            score += 100
            reasons.append("dmrl_title_exact")
        elif any(line.startswith(normalized_title) for line in normalized_lines):
            score += 70
            reasons.append("dmrl_title_prefix")
        elif any(normalized_title in line for line in normalized_lines):
            score += 45
            reasons.append("dmrl_title_contains")

    if any(_CHAPTER.search(line) for line in lines):
        score += 45
        reasons.append("chapter_1")

    text_chars = len(" ".join(lines))
    score += min(text_chars / 80.0, 20.0)
    if text_chars >= 180:
        score += 10
        reasons.append("text_density")
    elif text_chars < 40:
        score -= 20
        reasons.append("low_text_density")

    toc_lines = sum(bool(_TOC_LINE.search(line)) for line in lines)
    if toc_lines >= 2:
        score -= min(45.0, 15.0 * toc_lines)
        reasons.append("toc_like_lines")
    if any(normalize(line) in {"sommaire", "table des matieres", "contents", "table of contents"} for line in lines[:5]):
        score -= 30
        reasons.append("toc_heading")

    return round(score, 2), reasons


def detect_start_pages(doc: Document) -> list[dict]:
    """Retourne les pages candidates, classees par score decroissant."""
    if doc.source_format != "pdf":
        raise AppError("PDF_CUT_UNSUPPORTED", "La decoupe avant chapitre concerne uniquement les PDF.", 422)
    path = Path(doc.storage_path)
    if not path.exists():
        raise AppError("DOCUMENT_NOT_FOUND", "PDF source introuvable.", 404)
    title = _first_dm_title(doc)
    source = fitz.open(str(path))
    try:
        candidates = []
        for index, page in enumerate(source, start=1):
            text = _page_text(page)
            score, reasons = _score_page(text, title)
            if score > 0 or index == 1:
                candidates.append({
                    "page": index,
                    "score": score,
                    "reasons": reasons,
                    "preview": text[:500],
                })
        candidates.sort(key=lambda item: (-item["score"], item["page"]))
        return candidates or [{"page": 1, "score": 0, "reasons": [], "preview": ""}]
    finally:
        source.close()


def preview_page(doc: Document, page_number: int) -> bytes:
    path = Path(doc.storage_path)
    source = fitz.open(str(path))
    try:
        if not 1 <= page_number <= source.page_count:
            raise AppError("PDF_PAGE_INVALID", "Numero de page invalide.", 422)
        pixmap = source[page_number - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        return pixmap.tobytes("png")
    finally:
        source.close()


def cut_from_page(doc: Document, start_page: int, end_page: int | None = None) -> str:
    path = Path(doc.storage_path)
    source = fitz.open(str(path))
    total_pages = source.page_count
    try:
        if not 1 <= start_page <= total_pages:
            raise AppError("PDF_PAGE_INVALID", "Numero de page de debut invalide.", 422)
        selected_end_page = total_pages if end_page is None else end_page
        if not 1 <= selected_end_page <= total_pages or start_page > selected_end_page:
            raise AppError("PDF_PAGE_INVALID", "La plage de pages est invalide.", 422)
        output = Path(settings.storage_dir) / f"document_{doc.id}_cut.pdf"
        output.parent.mkdir(parents=True, exist_ok=True)
        cut = fitz.open()
        try:
            cut.insert_pdf(source, from_page=start_page - 1, to_page=selected_end_page - 1)
            cut.save(str(output))
        finally:
            cut.close()
    finally:
        source.close()
    doc.pdf_cut_path = str(output)
    doc.pdf_cut_start_page = start_page
    doc.pdf_cut_end_page = selected_end_page
    doc.page_count = selected_end_page - start_page + 1
    return str(output)


def total_pages(doc: Document) -> int:
    path = Path(doc.storage_path)
    source = fitz.open(str(path))
    try:
        return source.page_count
    finally:
        source.close()


def prepare_source(
    doc: Document,
    db: Session,
    *,
    cut_pdf: bool = True,
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    """Retourne le PDF a analyser, en le coupant si demande par l'API."""
    if doc.source_format != "pdf":
        return doc.storage_path
    if not cut_pdf:
        return doc.storage_path
    if doc.pdf_cut_path and Path(doc.pdf_cut_path).exists():
        if (
            (start_page is None or start_page == doc.pdf_cut_start_page)
            and (end_page is None or end_page == doc.pdf_cut_end_page)
        ):
            return doc.pdf_cut_path
    if start_page is not None:
        cut_from_page(doc, start_page, end_page)
        db.flush()
        return doc.pdf_cut_path or doc.storage_path
    candidates = detect_start_pages(doc)
    if settings.pdf_cut_requires_validation:
        raise AppError(
            "PDF_CUT_VALIDATION_REQUIRED",
            "Validez la page de debut du chapitre avant de lancer l'analyse.",
            409,
        )
    cut_from_page(doc, int(candidates[0]["page"]), end_page)
    db.flush()
    return doc.pdf_cut_path or doc.storage_path
