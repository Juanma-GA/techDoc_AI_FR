from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from io import BytesIO
from time import perf_counter
from typing import TYPE_CHECKING

import truststore
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError

truststore.inject_into_ssl()

if TYPE_CHECKING:
    from simple_lama_inpainting import SimpleLama

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
LAMA_CROP_PADDING_PX = 256


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _format_server_timing(timings: dict[str, float]) -> str:
    return ", ".join(f"{name};dur={duration:.3f}" for name, duration in timings.items())


@lru_cache(maxsize=1)
def get_lama() -> SimpleLama:
    from simple_lama_inpainting import SimpleLama

    return SimpleLama()


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if os.environ.get("DESKTOP_PRELOAD_MODELS", "").strip().lower() in {"1", "true", "yes", "on"}:
        await asyncio.to_thread(get_lama)
    yield


app = FastAPI(title="Local LaMa inpainting service", lifespan=_lifespan)


def _open_source_image(image_bytes: bytes) -> Image.Image:
    with Image.open(BytesIO(image_bytes)) as source:
        source.load()
        oriented = ImageOps.exif_transpose(source)
        if "A" in oriented.getbands() or "transparency" in oriented.info:
            rgba = oriented.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            return Image.alpha_composite(background, rgba).convert("RGB")
        return oriented.convert("RGB")


def _open_mask(
    mask_bytes: bytes,
    image_size: tuple[int, int],
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    with Image.open(BytesIO(mask_bytes)) as source:
        source.load()
        if source.size != image_size:
            raise HTTPException(
                status_code=422, detail="Le masque doit avoir les mêmes dimensions que l'image."
            )

        rgba = source.convert("RGBA")
        alpha = rgba.getchannel("A")
        mask = alpha if alpha.getextrema()[0] < 255 else source.convert("L")
        binary_mask = mask.point(lambda value: 255 if value > 0 else 0)

    bounds = binary_mask.getbbox()
    if bounds is None:
        raise HTTPException(status_code=422, detail="Peins au moins une zone avec le pinceau.")
    return binary_mask, bounds


def _crop_box_around_mask(
    image_size: tuple[int, int],
    mask_bounds: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    image_width, image_height = image_size
    left, top, right, bottom = mask_bounds
    return (
        max(0, left - LAMA_CROP_PADDING_PX),
        max(0, top - LAMA_CROP_PADDING_PX),
        min(image_width, right + LAMA_CROP_PADDING_PX),
        min(image_height, bottom + LAMA_CROP_PADDING_PX),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/inpaint")
async def inpaint(
    image: UploadFile = File(...),
    mask: UploadFile = File(...),
) -> Response:
    total_started = perf_counter()
    timings: dict[str, float] = {}
    stage_started = perf_counter()
    image_bytes = await image.read(MAX_UPLOAD_BYTES + 1)
    mask_bytes = await mask.read(MAX_UPLOAD_BYTES + 1)
    timings["upload_read_ms"] = _elapsed_ms(stage_started)
    if len(image_bytes) > MAX_UPLOAD_BYTES or len(mask_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="L'image ou le masque dépasse la limite de 15 Mo.")
    if not image_bytes or not mask_bytes:
        raise HTTPException(status_code=400, detail="L'image et le masque doivent être renseignés.")

    try:
        stage_started = perf_counter()
        source_image = _open_source_image(image_bytes)
        binary_mask, mask_bounds = _open_mask(mask_bytes, source_image.size)
        timings["decode_mask_ms"] = _elapsed_ms(stage_started)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(status_code=400, detail="L'image ou le masque est invalide.") from error

    stage_started = perf_counter()
    crop_box = _crop_box_around_mask(source_image.size, mask_bounds)
    crop_image = source_image.crop(crop_box)
    crop_mask = binary_mask.crop(crop_box)
    timings["crop_ms"] = _elapsed_ms(stage_started)

    stage_started = perf_counter()
    lama = get_lama()
    timings["model_load_ms"] = _elapsed_ms(stage_started)

    stage_started = perf_counter()
    inpainted_crop = lama(crop_image, crop_mask)
    timings["inference_ms"] = _elapsed_ms(stage_started)
    if inpainted_crop.width < crop_image.width or inpainted_crop.height < crop_image.height:
        raise RuntimeError("Le modèle LaMa a renvoyé une image plus petite que le crop demandé.")
    if inpainted_crop.size != crop_image.size:
        inpainted_crop = inpainted_crop.crop((0, 0, crop_image.width, crop_image.height))

    stage_started = perf_counter()
    inpainted_image = source_image.copy()
    inpainted_image.paste(inpainted_crop, crop_box[:2], crop_mask)
    timings["merge_ms"] = _elapsed_ms(stage_started)

    stage_started = perf_counter()
    output = BytesIO()
    inpainted_image.save(output, format="PNG", optimize=True)
    output_bytes = output.getvalue()
    timings["png_encode_ms"] = _elapsed_ms(stage_started)
    timings["total_ms"] = _elapsed_ms(total_started)
    crop_width = crop_box[2] - crop_box[0]
    crop_height = crop_box[3] - crop_box[1]
    return Response(
        content=output_bytes,
        media_type="image/png",
        headers={
            "Server-Timing": _format_server_timing(timings),
            "X-Lama-Image-Size": f"{source_image.width}x{source_image.height}",
            "X-Lama-Crop-Size": f"{crop_width}x{crop_height}",
            "X-Lama-Crop-Box": ",".join(str(value) for value in crop_box),
        },
    )
