from __future__ import annotations

import base64
from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, FiniteFloat, ValidationError

from app.services.constants import (
    A4_DPI,
    A4_HEIGHT,
    A4_WIDTH,
    MAX_IMAGE_BYTES,
    MAX_REPLACEMENT_FONT_SIZE,
    SUPPORTED_FORMATS,
)
from app.services.image_replacement import apply_replacements
from app.services.ocr_engine import normalize_reference

router = APIRouter(prefix="/image-processor", tags=["image-processor"])


class RecognizedLineIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    box: list[tuple[FiniteFloat, FiniteFloat]] = Field(min_length=4, max_length=4)


def _parse_line(raw_line: str) -> RecognizedLineIn:
    try:
        return RecognizedLineIn.model_validate_json(raw_line)
    except (ValueError, ValidationError) as error:
        raise HTTPException(status_code=422, detail="La ligne OCR est invalide.") from error


def _open_a4_image(image_bytes: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format
            image_size = image.size
            image.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
        raise HTTPException(
            status_code=400, detail="Le fichier fourni n'est pas une image valide.",
        ) from error

    if SUPPORTED_FORMATS.get(image_format or "") is None:
        raise HTTPException(status_code=415, detail="Formats acceptés : PNG, JPEG, WEBP, BMP et TIFF.")
    if image_size != (A4_WIDTH, A4_HEIGHT):
        raise HTTPException(status_code=422, detail="L'image de travail doit être au format A4.")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            return image.convert("RGB")
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
        raise HTTPException(
            status_code=400, detail="Le fichier fourni n'est pas une image valide.",
        ) from error


@router.post("/replace-line")
async def replace_recognized_line(
    image: UploadFile = File(...),
    line_json: str = Form(..., max_length=16_384),
    reference: str = Form(..., min_length=1, max_length=500),
    replacement: str = Form(..., min_length=1, max_length=500),
    replacement_font_size: int | None = Form(
        default=None, ge=1, le=MAX_REPLACEMENT_FONT_SIZE,
    ),
) -> dict[str, object]:
    image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="L'image dépasse la limite de 15 Mo.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Le fichier image est vide.")

    line = _parse_line(line_json)
    reference = reference.strip()
    replacement = replacement.strip()
    normalized_reference = normalize_reference(reference)
    if not normalized_reference or normalized_reference not in normalize_reference(line.text):
        raise HTTPException(status_code=422, detail="La référence n'est pas présente dans la ligne OCR.")
    if not replacement:
        raise HTTPException(status_code=422, detail="Le nouveau repère ne peut pas être vide.")
    if any(
        x < 0 or x > A4_WIDTH or y < 0 or y > A4_HEIGHT
        for x, y in line.box
    ):
        raise HTTPException(status_code=422, detail="La boîte OCR est hors de l'image.")

    source_image = _open_a4_image(image_bytes)
    rendered_image, replacement_counts, font_size = apply_replacements(
        source_image,
        [{"text": line.text, "box": [list(point) for point in line.box]}],
        [{"reference": reference, "replacement": replacement}],
        replacement_font_size,
    )
    replacement_count = replacement_counts[0]
    if replacement_count == 0:
        raise HTTPException(status_code=422, detail="La référence n'a pas de zone de texte remplaçable.")

    output = BytesIO()
    rendered_image.save(output, format="JPEG", quality=95, optimize=True, dpi=(A4_DPI, A4_DPI))
    encoded_image = base64.b64encode(output.getvalue()).decode("ascii")
    return {
        "edited_image": f"data:image/jpeg;base64,{encoded_image}",
        "replacement_count": replacement_count,
        "replacement_font_size": font_size,
    }
