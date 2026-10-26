"""Estimate visible character height, then choose one dominant font size."""

from __future__ import annotations

import os
from math import ceil
from pathlib import Path
from statistics import mean

from fastapi import HTTPException
from PIL import Image, ImageChops, ImageFont

from app.services.text_geometry import text_frame

ReplacementFont = ImageFont.FreeTypeFont | ImageFont.ImageFont


def load_replacement_font(size: int) -> ReplacementFont:
    windows_directory = os.environ.get("WINDIR")
    if windows_directory:
        font_path = Path(windows_directory) / "Fonts" / "arial.ttf"
        if font_path.is_file():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default(size=size)


def dominant_height(heights: list[float]) -> float:
    if not heights:
        raise HTTPException(status_code=422, detail="Impossible de mesurer la hauteur des caracteres.")
    groups: list[list[float]] = []
    for height in sorted(heights):
        if not groups or height - mean(groups[-1]) > max(2, mean(groups[-1]) * 0.1):
            groups.append([height])
        else:
            groups[-1].append(height)
    # Ties choose the smaller dominant group rather than enlarging arbitrarily.
    return mean(max(groups, key=len))


def _ink_components(mask: Image.Image) -> list[tuple[int, tuple[int, int, int, int]]]:
    width, height = mask.size
    pixels = bytearray(mask.tobytes())
    components: list[tuple[int, tuple[int, int, int, int]]] = []
    for index, value in enumerate(pixels):
        if not value:
            continue
        pixels[index] = 0
        queue = [index]
        y, x = divmod(index, width)
        left = right = x
        top = bottom = y
        for position in queue:
            y, x = divmod(position, width)
            left, right = min(left, x), max(right, x)
            top, bottom = min(top, y), max(bottom, y)
            for next_y in range(max(0, y - 1), min(height, y + 2)):
                for next_x in range(max(0, x - 1), min(width, x + 2)):
                    neighbor = next_y * width + next_x
                    if pixels[neighbor]:
                        pixels[neighbor] = 0
                        queue.append(neighbor)
        if len(queue) >= 3 and bottom - top >= 1:
            components.append((len(queue), (left, top, right + 1, bottom + 1)))
    return components


def measure_character_bounds(
    image: Image.Image, polygon: list[list[float]], background: tuple[int, int, int],
) -> tuple[int, int] | None:
    frame = text_frame(polygon)
    size = (max(1, ceil(frame.width)), max(1, ceil(frame.height)))
    # Pillow QUAD order is TL, BL, BR, TR, unlike the OCR reading-order polygon.
    coordinates = tuple(value for index in (0, 3, 2, 1) for value in polygon[index])
    crop = image.transform(
        size, Image.Transform.QUAD, coordinates, Image.Resampling.BICUBIC, fillcolor=background,
    )
    difference = ImageChops.difference(crop, Image.new("RGB", size, background)).convert("L")
    contrast = difference.getextrema()[1]
    if contrast < 24:
        return None
    threshold = max(24, ceil(contrast * 0.25))
    mask = difference.point([255 if value >= threshold else 0 for value in range(256)])
    components = _ink_components(mask)
    thin_horizontal_rules = [
        (area, box) for area, box in components
        if box[3] - box[1] <= max(2, ceil(size[1] * 0.12))
        and box[2] - box[0] >= max(4, size[0] * 0.25)
    ]
    text_components = [component for component in components if component not in thin_horizontal_rules]
    if text_components:
        components = text_components
    elif thin_horizontal_rules:
        return None
    interior = [
        (area, box) for area, box in components
        if not (
            box[3] - box[1] >= size[1] * 0.9
            and box[2] - box[0] <= max(2, size[0] * 0.03)
            and (box[1] == 0 or box[3] == size[1])
        )
    ]
    if interior:
        components = interior
    if not components:
        return None
    typical = dominant_height([float(box[3] - box[1]) for _, box in components])
    letters = [box for _, box in components if typical * 0.6 <= box[3] - box[1] <= typical * 1.7]
    if not letters:
        return None
    return min(box[1] for box in letters), max(box[3] for box in letters)


def measure_character_height(
    image: Image.Image, polygon: list[list[float]], background: tuple[int, int, int],
) -> float | None:
    bounds = measure_character_bounds(image, polygon, background)
    return float(bounds[1] - bounds[0]) if bounds is not None else None


def font_size_for_height(height: float) -> int:
    low, high = 1, max(1, ceil(height * 2) + 2)
    best_size, best_error = 1, float("inf")
    while low <= high:
        size = (low + high) // 2
        box = load_replacement_font(size).getbbox("H0")
        actual_height = box[3] - box[1]
        error = abs(actual_height - height)
        if (error, size) < (best_error, best_size):
            best_size, best_error = size, error
        if actual_height < height:
            low = size + 1
        else:
            high = size - 1
    return best_size
