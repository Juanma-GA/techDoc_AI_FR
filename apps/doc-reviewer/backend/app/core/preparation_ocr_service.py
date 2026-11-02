from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import fitz
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ocr_providers import run_ocr
from app.core.pdf_versioning import current_path
from app.core.preparation_classification import reset_page_decisions
from app.core.preparation_state import _find_page, _load_json, _load_validation_map
from app.db.models import Document
from app.db.preparation_models import DocumentPreparation


def run_document_ocr(
    db: Session,
    document: Document,
    record: DocumentPreparation,
) -> dict[str, Any]:
    page_metadata = _load_json(record.page_metadata_json, "page_metadata_json")
    existing_results = _load_json(record.ocr_results_json, "ocr_results_json").get(
        "mistral", {}
    )
    pages_to_ocr = [
        int(metadata["page"])
        for metadata in page_metadata
        if metadata.get("needs_ocr")
        and str(metadata["page"]) not in existing_results
    ]
    elapsed_ms = 0
    for page_number in pages_to_ocr:
        result = run_page_ocr(db, document, record, page_number, "mistral")
        elapsed_ms += result["elapsed_ms"]
    return {
        "provider": "mistral",
        "page_count": len(pages_to_ocr),
        "elapsed_ms": elapsed_ms,
    }


def run_page_ocr(
    db: Session,
    document: Document,
    record: DocumentPreparation,
    page_number: int,
    provider: str,
) -> dict[str, Any]:
    pages = _load_json(record.page_metadata_json, "page_metadata_json")
    metadata = _find_page(pages, page_number)
    if not metadata["needs_ocr"]:
        raise AppError(
            "OCR_PAGE_NOT_SELECTED",
            "Cette page n'est pas marquée comme nécessitant un OCR.",
            status_code=409,
        )
    try:
        with fitz.open(current_path(document.storage_dir, document.current_version)) as pdf:
            if not 1 <= page_number <= pdf.page_count:
                raise AppError("PAGE_RANGE_INVALID", "Numéro de page invalide.", status_code=422)
            page = pdf.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_bytes = pixmap.tobytes("png")
            width, height = pixmap.width, pixmap.height
    except AppError:
        raise
    except (fitz.FileDataError, RuntimeError, ValueError) as exc:
        raise AppError(
            "PREPARATION_DOCUMENT_INVALID",
            "Le document ne peut pas être rendu pour l'OCR.",
            status_code=400,
        ) from exc
    result = run_ocr(provider, image_bytes, width, height, db)
    ocr_results = _load_json(record.ocr_results_json, "ocr_results_json")
    provider_results = ocr_results.setdefault(provider, {})
    serialized = {
        "page": page_number,
        "provider": result.provider,
        "text": result.text,
        "boxes": [
            {
                "x0": box.x0,
                "y0": box.y0,
                "x1": box.x1,
                "y1": box.y1,
                "text": box.text,
                "confidence": box.confidence,
            }
            for box in result.boxes
        ],
        "elapsed_ms": result.elapsed_ms,
    }
    provider_results[str(page_number)] = serialized
    record.ocr_results_json = json.dumps(ocr_results, ensure_ascii=False)
    reset_page_decisions(record)
    validated_by_provider = _load_validation_map(record)
    validated_pages = set(validated_by_provider.get(provider, []))
    validated_pages.discard(page_number)
    validated_by_provider[provider] = sorted(validated_pages)
    record.validated_pages_json = json.dumps(validated_by_provider)
    record.updated_at = datetime.now(UTC)
    db.commit()
    return serialized


def get_native_page_text(
    document: Document,
    record: DocumentPreparation,
    page_number: int,
) -> dict[str, Any]:
    pages = _load_json(record.page_metadata_json, "page_metadata_json")
    metadata = _find_page(pages, page_number)
    if metadata["needs_ocr"]:
        raise AppError(
            "NATIVE_TEXT_UNAVAILABLE",
            "Cette page doit être lue avec un moteur OCR.",
            status_code=409,
        )
    try:
        with fitz.open(current_path(document.storage_dir, document.current_version)) as pdf:
            if not 1 <= page_number <= pdf.page_count:
                raise AppError("PAGE_RANGE_INVALID", "Numéro de page invalide.", status_code=422)
            text = pdf.load_page(page_number - 1).get_text("text") or ""
    except AppError:
        raise
    except (fitz.FileDataError, OSError, RuntimeError, ValueError) as exc:
        raise AppError(
            "PREPARATION_DOCUMENT_INVALID",
            "Le document PDF ne peut pas être lu pour la préparation.",
            status_code=400,
        ) from exc
    return {"page": page_number, "text": text}
