"""Background-preserving, centered text rendering in its detected orientation."""

from __future__ import annotations

from math import ceil, floor

from fastapi import HTTPException
from PIL import Image, ImageDraw

from app.services.replacement_typography import load_replacement_font
from app.services.text_geometry import snapped_angle, text_frame


def _histogram_median(histogram: list[int]) -> int:
    count = sum(histogram)
    if not count:
        raise HTTPException(status_code=422, detail="Impossible d'estimer le fond du repere.")
    lower = (count - 1) // 2
    upper = count // 2
    cumulative = 0
    lower_value = 0
    for value, frequency in enumerate(histogram):
        previous = cumulative
        cumulative += frequency
        if previous <= lower < cumulative:
            lower_value = value
        if previous <= upper < cumulative:
            return (lower_value + value) // 2
    raise RuntimeError("Invalid background histogram.")


def _sample_background_color(
    image: Image.Image, polygon: list[list[float]],
) -> tuple[int, int, int]:
    left = floor(min(point[0] for point in polygon))
    top = floor(min(point[1] for point in polygon))
    right = ceil(max(point[0] for point in polygon))
    bottom = ceil(max(point[1] for point in polygon))
    padding = max(2, ceil((bottom - top + 1) * 0.2))
    crop_left, crop_top = max(0, left - padding), max(0, top - padding)
    crop_right = min(image.width, right + padding + 1)
    crop_bottom = min(image.height, bottom + padding + 1)
    if crop_right <= crop_left or crop_bottom <= crop_top:
        raise HTTPException(status_code=422, detail="La zone du repere est hors de l'image.")
    crop = image.crop((crop_left, crop_top, crop_right, crop_bottom)).convert("RGB")
    mask = Image.new("L", crop.size, 255)
    ImageDraw.Draw(mask).polygon(
        [(point[0] - crop_left, point[1] - crop_top) for point in polygon], fill=0,
    )
    if mask.getbbox() is None:
        ImageDraw.Draw(mask).rectangle((0, 0, crop.width - 1, crop.height - 1), outline=255)
    red, green, blue = (_histogram_median(channel.histogram(mask=mask)) for channel in crop.split())
    return red, green, blue


def _draw_replacement_text(
    image: Image.Image, polygon: list[list[float]], text: str, fill: tuple[int, int, int],
    *, font_size: int,
) -> int:
    frame = text_frame(polygon)
    available_width = max(1, floor(frame.width * 0.92))
    font = load_replacement_font(font_size)
    box = font.getbbox(text)
    if box[2] - box[0] > available_width:
        low, high = 1, font_size - 1
        fitted_size = 0
        while low <= high:
            candidate = (low + high) // 2
            candidate_box = load_replacement_font(candidate).getbbox(text)
            if candidate_box[2] - candidate_box[0] <= available_width:
                fitted_size = candidate
                low = candidate + 1
            else:
                high = candidate - 1
        if not fitted_size:
            raise HTTPException(status_code=422, detail="Un nouveau repere est trop long pour sa zone.")
        font_size = fitted_size
        font = load_replacement_font(font_size)
        box = font.getbbox(text)
    width, height = box[2] - box[0], box[3] - box[1]
    if width < 1 or height < 1:
        raise HTTPException(status_code=422, detail="Un nouveau repere ne contient aucun caractere visible.")
    padding = 3
    layer = Image.new("RGBA", (width + padding * 2, height + padding * 2))
    ImageDraw.Draw(layer).text(
        (padding - box[0], padding - box[1]), text, font=font, fill=(*fill, 255),
    )
    rotated = layer.rotate(
        -snapped_angle(frame.angle), resample=Image.Resampling.BICUBIC, expand=True,
    )
    ink_bounds = rotated.getchannel("A").getbbox()
    if ink_bounds is None:
        raise HTTPException(status_code=422, detail="Un nouveau repere ne contient aucun caractere visible.")
    rotated = rotated.crop(ink_bounds)
    position = (
        round(frame.center[0] - rotated.width / 2),
        round(frame.center[1] - rotated.height / 2),
    )
    image.paste(rotated, position, rotated)
    return font_size
