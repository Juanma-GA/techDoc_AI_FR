from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.core.ocr_local import local_provider_available, run_indra_ocr, run_paddle_ocr
from app.core.ocr_mistral import run_mistral_ocr
from app.core.ocr_types import OcrPageResult


def available_providers() -> list[dict[str, Any]]:
    paddle_available = local_provider_available("paddle")
    indra_available = local_provider_available("indra")
    return [
        {
            "id": "mistral",
            "label": "Mistral OCR",
            "available": True,
            "external": True,
            "reason": None,
        },
        {
            "id": "paddle",
            "label": "PaddleOCR PP-OCRv6 tiny",
            "available": paddle_available,
            "external": False,
            "reason": None if paddle_available else (
                "PADDLEOCR_PYTHON_NOT_FOUND"
                if settings.paddleocr_python.strip()
                else "PADDLEOCR_NOT_INSTALLED_IN_BACKEND_ENV"
            ),
        },
        {
            "id": "indra",
            "label": "Indra OCR",
            "available": indra_available and settings.indra_ocr_license_approved,
            "external": False,
            "reason": (
                "INDRA_OCR_LICENSE_NOT_CONFIRMED"
                if not settings.indra_ocr_license_approved
                else None if indra_available else "INDRA_OCR_NOT_INSTALLED"
            ),
        },
    ]


def run_ocr(
    provider: str,
    image_bytes: bytes,
    image_width: int,
    image_height: int,
    db: Session,
) -> OcrPageResult:
    started = time.monotonic()
    if provider == "mistral":
        text, boxes = run_mistral_ocr(image_bytes, image_width, image_height, db)
    elif provider == "paddle":
        text, boxes = run_paddle_ocr(image_bytes, image_width, image_height)
    elif provider == "indra":
        if not settings.indra_ocr_license_approved:
            raise AppError(
                "INDRA_OCR_LICENSE_NOT_CONFIRMED",
                "L'utilisation des poids Indra OCR doit être autorisée avant son activation.",
                status_code=403,
            )
        text, boxes = run_indra_ocr(image_bytes, image_width, image_height)
    else:
        raise AppError("OCR_PROVIDER_INVALID", "Moteur OCR inconnu.", status_code=422)
    return OcrPageResult(
        text=text,
        boxes=boxes,
        provider=provider,
        elapsed_ms=max(0, round((time.monotonic() - started) * 1000)),
    )
