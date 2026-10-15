from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from typing import TYPE_CHECKING

import truststore
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError

truststore.inject_into_ssl()

if TYPE_CHECKING:
    from simple_lama_inpainting import SimpleLama

MAX_UPLOAD_BYTES = 15 * 1024 * 1024

app = FastAPI(title="Local LaMa inpainting service")


@lru_cache(maxsize=1)
def get_lama() -> SimpleLama:
    from simple_lama_inpainting import SimpleLama

    return SimpleLama()


def _open_source_image(image_bytes: bytes) -> Image.Image:
    with Image.open(BytesIO(image_bytes)) as source:
        source.load()
        oriented = ImageOps.exif_transpose(source)
        if "A" in oriented.getbands() or "transparency" in oriented.info:
            rgba = oriented.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            return Image.alpha_composite(background, rgba).convert("RGB")
        return oriented.convert("RGB")


def _open_mask(mask_bytes: bytes, image_size: tuple[int, int]) -> Image.Image:
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

    if binary_mask.getbbox() is None:
        raise HTTPException(status_code=422, detail="Peins au moins une zone avec le pinceau.")
    return binary_mask


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/inpaint")
async def inpaint(
    image: UploadFile = File(...),
    mask: UploadFile = File(...),
) -> Response:
    image_bytes = await image.read(MAX_UPLOAD_BYTES + 1)
    mask_bytes = await mask.read(MAX_UPLOAD_BYTES + 1)
    if len(image_bytes) > MAX_UPLOAD_BYTES or len(mask_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="L'image ou le masque dépasse la limite de 15 Mo.")
    if not image_bytes or not mask_bytes:
        raise HTTPException(status_code=400, detail="L'image et le masque doivent être renseignés.")

    try:
        source_image = _open_source_image(image_bytes)
        binary_mask = _open_mask(mask_bytes, source_image.size)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(status_code=400, detail="L'image ou le masque est invalide.") from error

    inpainted_image = get_lama()(source_image, binary_mask)
    output = BytesIO()
    inpainted_image.save(output, format="PNG", optimize=True)
    return Response(content=output.getvalue(), media_type="image/png")
