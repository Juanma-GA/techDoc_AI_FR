from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.constants import A4_DPI, A4_HEIGHT, A4_WIDTH, SUPPORTED_FORMATS


def _safe_filename_component(value: str) -> str:
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().rstrip(" .")
    if not safe_name:
        raise HTTPException(
            status_code=422, detail="Le nom ICN ne peut pas produire un nom de fichier valide."
        )
    if safe_name.split(".")[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }:
        safe_name = f"_{safe_name}"
    return safe_name


def output_filename(image_filename: str | None, icn: str | None) -> str:
    if icn is not None:
        stem = re.sub(r"\.jpe?g$", "", icn.strip(), flags=re.I)
        return f"{_safe_filename_component(stem)}.jpg"
    image_stem = Path(image_filename or "image").stem or "image"
    return f"{_safe_filename_component(image_stem)}-modifiee.jpg"


def image_on_white(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    background.alpha_composite(rgba)
    return background.convert("RGB")


def prepare_source_image(image_bytes: bytes) -> tuple[Image.Image, bytes]:
    with Image.open(BytesIO(image_bytes)) as source_image:
        oriented_image = ImageOps.exif_transpose(source_image)
        normalized_image = image_on_white(oriented_image)

    encoded_image = BytesIO()
    normalized_image.save(encoded_image, format="PNG", optimize=True)
    return normalized_image, encoded_image.getvalue()


def create_a4_page(image: Image.Image) -> tuple[Image.Image, float, float, int, int]:
    source = image_on_white(image)
    scale = min(A4_WIDTH / source.width, A4_HEIGHT / source.height)
    resized_width = max(1, min(A4_WIDTH, round(source.width * scale)))
    resized_height = max(1, min(A4_HEIGHT, round(source.height * scale)))
    resized = source.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
    left = (A4_WIDTH - resized_width) // 2
    top = (A4_HEIGHT - resized_height) // 2

    page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
    page.paste(resized, (left, top))
    return page, resized_width / source.width, resized_height / source.height, left, top


def export_jpeg(image_bytes: bytes) -> bytes:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            if image.format not in SUPPORTED_FORMATS:
                raise HTTPException(status_code=415, detail="Format d'image non pris en charge.")
            print_ready = (
                image.format == "JPEG" and image.mode == "RGB"
                and image.size == (A4_WIDTH, A4_HEIGHT)
                and image.info.get("dpi") == (A4_DPI, A4_DPI) and not image.getexif()
            )
            if print_ready:
                image.load()
            else:
                image.verify()
        if print_ready:
            return image_bytes
        source, _ = prepare_source_image(image_bytes)
        page, *_ = create_a4_page(source)
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise HTTPException(status_code=400, detail="Le fichier image est invalide.") from error
    encoded = BytesIO()
    page.save(encoded, format="JPEG", quality=95, dpi=(A4_DPI, A4_DPI))
    return encoded.getvalue()
