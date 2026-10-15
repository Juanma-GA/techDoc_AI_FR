from __future__ import annotations

import base64

import requests
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.services.constants import LAMA_SERVICE_TIMEOUT, MAX_IMAGE_BYTES

router = APIRouter(prefix="/image-replace", tags=["image-replace"])


@router.post("/inpaint")
def inpaint_image(
    image: UploadFile = File(...),
    mask: UploadFile = File(...),
) -> dict[str, str]:
    image_bytes = image.file.read(MAX_IMAGE_BYTES + 1)
    mask_bytes = mask.file.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES or len(mask_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="L'image ou le masque dépasse la limite de 15 Mo.")
    if not image_bytes or not mask_bytes:
        raise HTTPException(status_code=400, detail="L'image et le masque doivent être renseignés.")

    try:
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
            encoded_image = base64.b64encode(response.content).decode("ascii")
    except requests.exceptions.ConnectionError as error:
        raise HTTPException(
            status_code=503,
            detail="Le service LaMa n'est pas démarré. Lance-le sur le port 8011.",
        ) from error
    except requests.exceptions.Timeout as error:
        raise HTTPException(
            status_code=504, detail="Le traitement LaMa a dépassé le délai autorisé."
        ) from error

    return {"edited_image": f"data:image/png;base64,{encoded_image}"}
