from __future__ import annotations

import base64
from time import perf_counter

import requests
import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.services.constants import LAMA_SERVICE_TIMEOUT, MAX_IMAGE_BYTES

router = APIRouter(prefix="/image-processor", tags=["image-processor"])
log = structlog.get_logger(__name__)


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


@router.post("/inpaint")
def inpaint_image(
    image: UploadFile = File(...),
    mask: UploadFile = File(...),
) -> dict[str, str]:
    total_started = perf_counter()
    stage_started = perf_counter()
    image_bytes = image.file.read(MAX_IMAGE_BYTES + 1)
    image_read_ms = _elapsed_ms(stage_started)
    stage_started = perf_counter()
    mask_bytes = mask.file.read(MAX_IMAGE_BYTES + 1)
    mask_read_ms = _elapsed_ms(stage_started)
    if len(image_bytes) > MAX_IMAGE_BYTES or len(mask_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="L'image ou le masque dépasse la limite de 15 Mo.")
    if not image_bytes or not mask_bytes:
        raise HTTPException(status_code=400, detail="L'image et le masque doivent être renseignés.")

    try:
        stage_started = perf_counter()
        with requests.post(
            f"http://127.0.0.1:{settings.lama_service_port}/inpaint",
            files={
                "image": (
                    image.filename or "image.png",
                    image_bytes,
                    image.content_type or "application/octet-stream",
                ),
                "mask": (
                    mask.filename or "mask.png",
                    mask_bytes,
                    mask.content_type or "application/octet-stream",
                ),
            },
            timeout=LAMA_SERVICE_TIMEOUT,
        ) as response:
            if response.status_code >= 400:
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                detail = payload.get("detail") if isinstance(payload, dict) else None
                status_code = response.status_code if response.status_code < 500 else 502
                raise HTTPException(
                    status_code=status_code,
                    detail=detail
                    if isinstance(detail, str)
                    else "Le service LaMa n'a pas pu traiter l'image.",
                )
            if response.headers.get("content-type", "").split(";", 1)[0].lower() != "image/png":
                raise HTTPException(status_code=502, detail="Le service LaMa a renvoyé un format inattendu.")
            response_bytes = response.content
            server_timing = response.headers.get("server-timing")
            image_size = response.headers.get("x-lama-image-size")
            crop_size = response.headers.get("x-lama-crop-size")
            crop_box = response.headers.get("x-lama-crop-box")
        upstream_ms = _elapsed_ms(stage_started)
    except requests.exceptions.ConnectionError as error:
        raise HTTPException(
            status_code=503,
            detail="Le service LaMa n'est pas démarré. Lance-le sur le port 8011.",
        ) from error
    except requests.exceptions.Timeout as error:
        raise HTTPException(
            status_code=504, detail="Le traitement LaMa a dépassé le délai autorisé."
        ) from error

    stage_started = perf_counter()
    encoded_image = base64.b64encode(response_bytes).decode("ascii")
    base64_encode_ms = _elapsed_ms(stage_started)
    log.info(
        "image_inpaint_timing",
        total_ms=_elapsed_ms(total_started),
        image_read_ms=image_read_ms,
        mask_read_ms=mask_read_ms,
        upstream_ms=upstream_ms,
        base64_encode_ms=base64_encode_ms,
        input_image_bytes=len(image_bytes),
        input_mask_bytes=len(mask_bytes),
        output_image_bytes=len(response_bytes),
        lama_server_timing=server_timing,
        image_size=image_size,
        crop_size=crop_size,
        crop_box=crop_box,
    )
    return {"edited_image": f"data:image/png;base64,{encoded_image}"}
