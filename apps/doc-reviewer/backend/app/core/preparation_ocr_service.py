from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import fitz
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ocr_mistral import run_mistral_ocr_document
from app.core.ocr_output import extract_result
from app.core.ocr_providers import run_ocr
from app.core.pdf_versioning import current_path
from app.core.preparation_state import _find_page, _load_json
from app.db.models import Document
from app.db.preparation_models import DocumentPreparation


def run_document_ocr(
    db: Session,
    document: Document,
    record: DocumentPreparation,
) -> dict[str, Any]:
    pdf_bytes = current_path(document.storage_dir, document.current_version).read_bytes()
    response, elapsed_ms = run_mistral_ocr_document(pdf_bytes, db)
    response_pages = response.get("pages")
    page_metadata = _load_json(record.page_metadata_json, "page_metadata_json")
    if not isinstance(response_pages, list) or len(response_pages) != len(page_metadata):
        raise AppError(
            "MISTRAL_OCR_PAGE_COUNT_MISMATCH",
            "Mistral OCR n'a pas renvoyé de résultat pour chaque page du document.",
            status_code=502,
            detail={
                "expected_pages": len(page_metadata),
                "returned_pages": len(response_pages) if isinstance(response_pages, list) else 0,
            },
        )

    results: dict[str, dict[str, Any]] = {}
    for page_number, (page_payload, metadata) in enumerate(
        zip(response_pages, page_metadata, strict=True),
        start=1,
    ):
        if not isinstance(page_payload, dict):
            raise AppError(
                "MISTRAL_OCR_RESPONSE_INVALID",
                "Un résultat de page Mistral OCR est invalide.",
                status_code=502,
            )
        dimensions = page_payload.get("dimensions")
        dimensions = dimensions if isinstance(dimensions, dict) else {}
        width = _positive_int(dimensions.get("width")) or round(float(metadata["width"]) * 200 / 72)
        height = _positive_int(dimensions.get("height")) or round(float(metadata["height"]) * 200 / 72)
        text, boxes = extract_result(
            page_payload,
            width,
            height,
            coordinate_mode="pixels",
        )
        results[str(page_number)] = {
            "page": page_number,
            "provider": "mistral",
            "text": text,
            "boxes": [
                {
                    "x0": box.x0,
                    "y0": box.y0,
                    "x1": box.x1,
                    "y1": box.y1,
                    "text": box.text,
                    "confidence": box.confidence,
                }
                for box in boxes
            ],
            "elapsed_ms": elapsed_ms,
        }

    record.ocr_results_json = json.dumps({"mistral": results}, ensure_ascii=False)
    record.selected_provider = "mistral"
    record.validated_pages_json = json.dumps({"mistral": []})
    record.updated_at = datetime.now(UTC)
    db.commit()
    return {"provider": "mistral", "page_count": len(results), "elapsed_ms": elapsed_ms}


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return round(value)


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
    record.updated_at = datetime.now(UTC)
    db.commit()
    return serialized
