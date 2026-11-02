"""Detection et decoupage du PDF avant le premier chapitre."""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf as fitz
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.core.fs import atomic_output_path, atomic_write_bytes
from app.core.pdf_cut_scoring import dmrl_data_module_titles
from app.core.pdf_cut_scoring import score_page as _score_page
from app.db.models import Document

_LIST_OF_TABLES = re.compile(r"\blist\s+of\s+tables\b", re.IGNORECASE)
_INTENTIONALLY_BLANK = re.compile(
    r"\bpage\s+intentionally\s+left\s+blank\b", re.IGNORECASE
)


def _page_text(page: fitz.Page) -> str:
    return (page.get_text("text") or "").strip()


def _is_blank_page(text: str) -> bool:
    return not text.strip() or bool(_INTENTIONALLY_BLANK.search(text))


def _start_page_after_tables_list(page_texts: list[str]) -> int | None:
    list_pages = [
        index for index, text in enumerate(page_texts) if _LIST_OF_TABLES.search(text)
    ]
    if not list_pages:
        return None

    boundary_index = list_pages[-1] + 1
    while boundary_index < len(page_texts):
        text = page_texts[boundary_index]
        if not _is_blank_page(text):
            break
        boundary_index += 1

    return boundary_index + 1 if boundary_index < len(page_texts) else None


def detect_start_pages(doc: Document, title: str | None = None) -> list[dict]:
    """Retourne les pages candidates, classees par score decroissant."""
    if doc.source_format != "pdf":
        raise AppError("PDF_CUT_UNSUPPORTED", "La decoupe avant chapitre concerne uniquement les PDF.", 422)
    path = Path(doc.storage_path)
    if not path.exists():
        raise AppError("DOCUMENT_NOT_FOUND", "PDF source introuvable.", 404)
    titles = dmrl_data_module_titles(doc.dmrl_json)
    if title is not None and title not in titles:
        raise AppError("PDF_DM_TITLE_INVALID", "Le titre selectionne ne figure pas dans la DMRL.", 422)
    scoring_title = title or next(iter(titles), "")
    source = fitz.open(str(path))
    try:
        candidates = []
        page_texts = [_page_text(page) for page in source]
        preferred_start_page = _start_page_after_tables_list(page_texts)
        for index, text in enumerate(page_texts, start=1):
            if _LIST_OF_TABLES.search(text):
                continue
            score, reasons = _score_page(text, scoring_title)
            if index == preferred_start_page:
                reasons.append("after_list_of_tables")
            candidate = {
                "page": index,
                "score": score,
                "reasons": reasons,
                "preview": text[:500],
            }
            if score > 0 or index == 1 or index == preferred_start_page:
                candidates.append(candidate)
        candidates.sort(key=lambda item: (
            -item["score"],
            item["page"] != preferred_start_page,
            item["page"],
        ))
        if not candidates:
            candidates = [{"page": 1, "score": 0, "reasons": [], "preview": ""}]

        first_page = candidates[0]["page"]
        selected_page = first_page
        while selected_page <= len(page_texts) and _is_blank_page(page_texts[selected_page - 1]):
            selected_page += 1
        if selected_page > len(page_texts):
            raise AppError(
                "PDF_START_PAGE_NOT_FOUND",
                "Aucune page non vide n'a ete trouvee apres la page candidate.",
                422,
            )
        if selected_page != first_page:
            text = page_texts[selected_page - 1]
            score, reasons = _score_page(text, scoring_title)
            if selected_page == preferred_start_page:
                reasons.append("after_list_of_tables")
            reasons.append("advanced_past_blank_page")
            advanced_candidate = {
                "page": selected_page,
                "score": score,
                "reasons": reasons,
                "preview": text[:500],
            }
            return [
                advanced_candidate,
                *(
                    candidate
                    for candidate in candidates
                    if candidate["page"] != selected_page
                    and not _is_blank_page(page_texts[candidate["page"] - 1])
                ),
            ]
        return [
            candidate
            for candidate in candidates
            if not _is_blank_page(page_texts[candidate["page"] - 1])
        ]
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


def previews_dir(doc: Document) -> Path:
    return Path(doc.storage_path).parent / f"document_{doc.id}_previews"


def preview_path(doc: Document, page_number: int) -> Path:
    if page_number < 1:
        raise AppError("PDF_PAGE_INVALID", "Numero de page invalide.", 422)
    stat = Path(doc.storage_path).stat()
    path = previews_dir(doc) / f"{stat.st_mtime_ns}_{stat.st_size}" / f"page_{page_number}_z15.png"
    if not path.is_file():
        atomic_write_bytes(path, preview_page(doc, page_number))
    return path


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
        output = Path(doc.storage_path).parent / f"document_{doc.id}_cut.pdf"
        output.parent.mkdir(parents=True, exist_ok=True)
        cut = fitz.open()
        try:
            cut.insert_pdf(source, from_page=start_page - 1, to_page=selected_end_page - 1)
            with atomic_output_path(output) as temporary:
                cut.save(str(temporary))
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
