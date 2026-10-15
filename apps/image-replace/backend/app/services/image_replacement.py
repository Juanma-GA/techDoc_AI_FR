from __future__ import annotations

import os
from math import ceil, floor
from pathlib import Path
from statistics import median
from typing import TypedDict

from PIL import Image, ImageDraw, ImageFont

from app.services.image_layout import image_on_white
from app.services.ocr_engine import _box_points, normalize_reference


class _ReplacementOccurrence(TypedDict):
    line_index: int
    pair_index: int
    reference: str
    start: int
    end: int
    polygon: list[list[float]]


def _normalized_text_with_positions(value: str) -> tuple[str, list[int]]:
    normalized_parts: list[str] = []
    positions: list[int] = []
    for index, character in enumerate(value):
        normalized_character = normalize_reference(character)
        normalized_parts.append(normalized_character)
        positions.extend([index] * len(normalized_character))
    return "".join(normalized_parts), positions


def _interpolate_point(start: list[float], end: list[float], ratio: float) -> list[float]:
    return [
        start[0] + (end[0] - start[0]) * ratio,
        start[1] + (end[1] - start[1]) * ratio,
    ]


def _replacement_segment(
    box: object, text_length: int, start_index: int, end_index: int
) -> list[list[float]]:
    points = _box_points(box)
    if len(points) < 4 or text_length <= 0:
        return []

    start_ratio = start_index / text_length
    end_ratio = end_index / text_length
    top_start = _interpolate_point(points[0], points[1], start_ratio)
    top_end = _interpolate_point(points[0], points[1], end_ratio)
    bottom_end = _interpolate_point(points[3], points[2], end_ratio)
    bottom_start = _interpolate_point(points[3], points[2], start_ratio)
    return [top_start, top_end, bottom_end, bottom_start]


def _pixel_rgb(pixel: object) -> tuple[int, int, int]:
    if isinstance(pixel, tuple):
        if len(pixel) < 3:
            raise ValueError("Impossible de lire la couleur du fond de l'image.")
        return int(pixel[0]), int(pixel[1]), int(pixel[2])
    if isinstance(pixel, (int, float)):
        channel = int(pixel)
        return channel, channel, channel
    raise ValueError("Impossible de lire la couleur du fond de l'image.")


def _sample_background_color(
    image: Image.Image,
    polygon: list[list[float]],
) -> tuple[int, int, int]:
    left = floor(min(point[0] for point in polygon))
    top = floor(min(point[1] for point in polygon))
    right = ceil(max(point[0] for point in polygon))
    bottom = ceil(max(point[1] for point in polygon))
    padding = max(2, ceil((bottom - top + 1) * 0.2))
    crop_left = max(0, left - padding)
    crop_top = max(0, top - padding)
    crop_right = min(image.width, right + padding + 1)
    crop_bottom = min(image.height, bottom + padding + 1)
    crop = image.crop((crop_left, crop_top, crop_right, crop_bottom))
    if crop.width == 0 or crop.height == 0:
        raise ValueError("Impossible d'estimer le fond autour du repère à remplacer.")

    mask = Image.new("1", crop.size)
    local_polygon = [
        [point[0] - crop_left, point[1] - crop_top]
        for point in polygon
    ]
    ImageDraw.Draw(mask).polygon(local_polygon, fill=1)

    samples: list[tuple[int, int, int]] = []
    for y in range(crop.height):
        for x in range(crop.width):
            if mask.getpixel((x, y)):
                continue
            samples.append(_pixel_rgb(crop.getpixel((x, y))))

    if not samples:
        for y in range(crop.height):
            for x in range(crop.width):
                if x not in {0, crop.width - 1} and y not in {0, crop.height - 1}:
                    continue
                samples.append(_pixel_rgb(crop.getpixel((x, y))))

    return (
        int(median(pixel[0] for pixel in samples)),
        int(median(pixel[1] for pixel in samples)),
        int(median(pixel[2] for pixel in samples)),
    )


def _load_replacement_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    windows_directory = os.environ.get("WINDIR")
    if windows_directory:
        font_path = Path(windows_directory) / "Fonts" / "arial.ttf"
        if font_path.is_file():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default(size=size)


def _draw_replacement_text(
    draw: ImageDraw.ImageDraw,
    polygon: list[list[float]],
    text: str,
    fill: tuple[int, ...],
) -> None:
    left = min(point[0] for point in polygon)
    top = min(point[1] for point in polygon)
    right = max(point[0] for point in polygon)
    bottom = max(point[1] for point in polygon)
    width = right - left
    height = bottom - top
    if width < 1 or height < 1:
        return

    font_size = max(1, int(height * 0.8))
    font = _load_replacement_font(font_size)
    text_box = draw.textbbox((0, 0), text, font=font)
    text_width = max(1, text_box[2] - text_box[0])
    text_height = max(1, text_box[3] - text_box[1])
    scale = min(1, width * 0.92 / text_width, height * 0.82 / text_height)
    if scale < 1:
        font = _load_replacement_font(max(1, int(font_size * scale)))

    draw.text(
        ((left + right) / 2, (top + bottom) / 2),
        text,
        fill=fill,
        font=font,
        anchor="mm",
    )


def apply_replacements(
    source_image: Image.Image,
    lines: list[dict[str, object]],
    replacement_pairs: list[dict[str, str]],
) -> tuple[Image.Image, list[int]]:
    applied_counts = [0] * len(replacement_pairs)
    pair_indices_by_reference: dict[str, list[int]] = {}
    for pair_index, pair in enumerate(replacement_pairs):
        normalized_reference = normalize_reference(pair["reference"])
        if not normalized_reference:
            raise ValueError("Une référence de remplacement ne peut pas être vide.")
        pair_indices_by_reference.setdefault(normalized_reference, []).append(pair_index)

    occurrences: list[_ReplacementOccurrence] = []

    for line_index, line in enumerate(lines):
        text = str(line["text"])
        normalized_text, positions = _normalized_text_with_positions(text)
        for normalized_reference, pair_indices in pair_indices_by_reference.items():
            search_offset = 0
            while True:
                start = normalized_text.find(normalized_reference, search_offset)
                if start < 0:
                    break
                end = start + len(normalized_reference)
                segment = _replacement_segment(
                    line.get("box", []),
                    len(text),
                    positions[start],
                    positions[end - 1] + 1,
                )
                if segment:
                    occurrences.append(
                        {
                            "line_index": line_index,
                            "pair_index": pair_indices[0],
                            "reference": normalized_reference,
                            "start": start,
                            "end": end,
                            "polygon": segment,
                        }
                    )
                search_offset = end

    occurrences.sort(
        key=lambda item: (
            item["line_index"],
            item["start"],
            -(item["end"] - item["start"]),
            item["pair_index"],
        )
    )

    accepted_by_reference: dict[str, list[_ReplacementOccurrence]] = {}
    occupied: dict[int, list[tuple[int, int]]] = {}
    for occurrence in occurrences:
        line_index = occurrence["line_index"]
        start = occurrence["start"]
        end = occurrence["end"]
        line_ranges = occupied.setdefault(line_index, [])
        if any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in line_ranges):
            continue

        line_ranges.append((start, end))
        reference = occurrence["reference"]
        accepted_by_reference.setdefault(reference, []).append(occurrence)

    accepted: list[_ReplacementOccurrence] = []
    for reference, reference_occurrences in accepted_by_reference.items():
        pair_indices = pair_indices_by_reference[reference]
        for occurrence_index, occurrence in enumerate(reference_occurrences):
            if len(pair_indices) == 1:
                pair_index = pair_indices[0]
            elif occurrence_index < len(pair_indices):
                pair_index = pair_indices[occurrence_index]
            else:
                continue

            occurrence["pair_index"] = pair_index
            accepted.append(occurrence)
            applied_counts[pair_index] += 1

    accepted.sort(key=lambda item: (item["line_index"], item["start"]))

    canvas = image_on_white(source_image)
    draw = ImageDraw.Draw(canvas)
    replacement_draws: list[tuple[list[list[float]], int, tuple[int, int, int]]] = []
    for occurrence in accepted:
        polygon = occurrence["polygon"]
        replacement_draws.append(
            (
                polygon,
                occurrence["pair_index"],
                _sample_background_color(canvas, polygon),
            )
        )

    for polygon, pair_index, background_color in replacement_draws:
        draw.polygon(polygon, fill=background_color)
        _draw_replacement_text(
            draw,
            polygon,
            replacement_pairs[pair_index]["replacement"],
            (0, 0, 0),
        )

    return canvas, applied_counts
