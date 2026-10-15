from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.image_layout import image_on_white
from app.services.ocr_engine import _box_points, normalize_reference


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


def _load_replacement_font(size: int) -> ImageFont.ImageFont:
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
    occurrences: list[dict[str, object]] = []

    for pair_index, pair in enumerate(replacement_pairs):
        normalized_reference = normalize_reference(pair["reference"])
        for line_index, line in enumerate(lines):
            text = str(line["text"])
            normalized_text, positions = _normalized_text_with_positions(text)
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
                            "pair_index": pair_index,
                            "start": start,
                            "end": end,
                            "polygon": segment,
                        }
                    )
                search_offset = end

    occurrences.sort(
        key=lambda item: (
            int(item["line_index"]),
            int(item["start"]),
            -(int(item["end"]) - int(item["start"])),
            int(item["pair_index"]),
        )
    )
    accepted: list[dict[str, object]] = []
    occupied: dict[int, list[tuple[int, int]]] = {}
    for occurrence in occurrences:
        line_index = int(occurrence["line_index"])
        start = int(occurrence["start"])
        end = int(occurrence["end"])
        line_ranges = occupied.setdefault(line_index, [])
        if any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in line_ranges):
            continue

        line_ranges.append((start, end))
        accepted.append(occurrence)
        applied_counts[int(occurrence["pair_index"])] += 1

    canvas = image_on_white(source_image)
    draw = ImageDraw.Draw(canvas)
    for occurrence in accepted:
        polygon = occurrence["polygon"]
        if not isinstance(polygon, list):
            continue
        draw.polygon(polygon, fill=(255, 255, 255))
        _draw_replacement_text(
            draw,
            polygon,
            replacement_pairs[int(occurrence["pair_index"])]["replacement"],
            (0, 0, 0),
        )

    return canvas, applied_counts
