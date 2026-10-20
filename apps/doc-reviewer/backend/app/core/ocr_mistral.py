from __future__ import annotations

import base64

import httpx
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.mistral_settings import get_endpoint, get_llm_enabled
from app.core.ocr_output import extract_result
from app.core.ocr_types import OcrBox


def run_mistral_ocr(
    image_bytes: bytes,
    image_width: int,
    image_height: int,
    db: Session,
) -> tuple[str, list[OcrBox]]:
    if not get_llm_enabled(db):
        raise AppError("LLM_DISABLED", "L'IA est désactivée dans les paramètres.", status_code=400)
    config = get_endpoint(db)
    if not config["api_key"]:
        raise AppError(
            "MISTRAL_NOT_CONFIGURED",
            "Configurez la clé API Mistral dans Paramètres pour utiliser Mistral OCR.",
            status_code=400,
        )
    payload = {
        "model": config.get("ocr_model") or "mistral-ocr-latest",
        "include_blocks": True,
        "confidence_scores_granularity": "block",
        "document": {
            "type": "image_url",
            "image_url": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
        },
    }
    try:
        with httpx.Client(timeout=120, follow_redirects=False) as client:
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
    return extract_result(
        response_payload,
        image_width,
        image_height,
        coordinate_mode="pixels",
    )
