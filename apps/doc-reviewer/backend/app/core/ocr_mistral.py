from __future__ import annotations

import base64
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.mistral_settings import get_endpoint, get_llm_enabled
from app.core.ocr_output import extract_result
from app.core.ocr_types import OcrBox


def _ocr_config(db: Session) -> dict[str, str]:
    if not get_llm_enabled(db):
        raise AppError("LLM_DISABLED", "L'IA est désactivée dans les paramètres.", status_code=400)
    config = get_endpoint(db)
    if not config["api_key"]:
        raise AppError(
            "MISTRAL_NOT_CONFIGURED",
            "Configurez une clé API Mistral dans Paramètres pour utiliser Mistral OCR.",
            status_code=400,
        )
    return config


def _post_ocr(config: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=300, follow_redirects=False) as client:
            response = client.post(
                f"{config['base_url'].rstrip('/')}/v1/ocr",
                headers={"Authorization": f"Bearer {config['api_key']}"},
                json=payload,
            )
    except httpx.RequestError as exc:
        raise AppError(
            "MISTRAL_OCR_CALL_FAILED",
            f"Échec de l'appel Mistral OCR : {type(exc).__name__}.",
            status_code=502,
        ) from exc
    if response.status_code != 200:
        raise AppError(
            "MISTRAL_OCR_CALL_FAILED",
            f"Mistral OCR a renvoyé HTTP {response.status_code}.",
            status_code=502,
        )
    try:
        response_payload = response.json()
    except ValueError as exc:
        raise AppError(
            "MISTRAL_OCR_RESPONSE_INVALID",
            "La réponse Mistral OCR n'est pas un JSON valide.",
            status_code=502,
        ) from exc
    if not isinstance(response_payload, dict):
        raise AppError(
            "MISTRAL_OCR_RESPONSE_INVALID",
            "La réponse Mistral OCR n'est pas un objet JSON.",
            status_code=502,
        )
    return response_payload


def _request_payload(config: dict[str, str], document: dict[str, str]) -> dict[str, Any]:
    return {
        "model": config.get("ocr_model") or "mistral-ocr-latest",
        "include_blocks": True,
        "confidence_scores_granularity": "block",
        "document": document,
    }


def run_mistral_ocr(
    image_bytes: bytes,
    image_width: int,
    image_height: int,
    db: Session,
) -> tuple[str, list[OcrBox]]:
    config = _ocr_config(db)
    payload = _request_payload(
        config,
        {
            "type": "image_url",
            "image_url": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
        },
    )
    response_payload = _post_ocr(config, payload)
    return extract_result(
        response_payload,
        image_width,
        image_height,
        coordinate_mode="pixels",
    )


def run_mistral_ocr_document(pdf_bytes: bytes, db: Session) -> tuple[dict[str, Any], int]:
    config = _ocr_config(db)
    payload = _request_payload(
        config,
        {
            "type": "document_url",
            "document_url": "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii"),
        },
    )
    started = time.monotonic()
    response_payload = _post_ocr(config, payload)
    elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
    if not isinstance(response_payload.get("pages"), list):
        raise AppError(
            "MISTRAL_OCR_RESPONSE_INVALID",
            "La réponse Mistral OCR ne contient pas de liste de pages.",
            status_code=502,
        )
    return response_payload, elapsed_ms
