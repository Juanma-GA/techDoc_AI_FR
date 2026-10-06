"""Detection des croix rouges ajoutees au-dessus des images PDF."""

from __future__ import annotations

import fitz

_CROSS_SYMBOLS = {"x", "×", "✕", "✖", "✗"}
_MIN_OVERLAY_CROSS_SIZE = 24.0


def is_large_red_image_cross(span: dict, image_rects: list[fitz.Rect]) -> bool:
    text = str(span.get("text", "")).strip().casefold()
    if text not in _CROSS_SYMBOLS:
        return False
    try:
        size = float(span.get("size", 0.0))
        color = int(span.get("color", 0))
        cross_rect = fitz.Rect(span["bbox"])
    except (KeyError, TypeError, ValueError):
        return False
    if size < _MIN_OVERLAY_CROSS_SIZE:
        return False
    red, green, blue = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
    if red < 160 or green > 100 or blue > 100:
        return False
    area = cross_rect.width * cross_rect.height
    if area <= 0:
        return False
    return any(
        (overlap := cross_rect & image_rect).width * overlap.height / area >= 0.5
        for image_rect in image_rects
    )


def large_red_cross_rects(blocks: list[dict], image_rects: list[fitz.Rect]) -> list[fitz.Rect]:
    return [
        fitz.Rect(span["bbox"])
        for block in blocks
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if is_large_red_image_cross(span, image_rects)
    ]