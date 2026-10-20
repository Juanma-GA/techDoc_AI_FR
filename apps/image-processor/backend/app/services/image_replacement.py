from __future__ import annotations

from math import hypot
from typing import TypedDict

import structlog
from PIL import Image, ImageDraw

from app.services.image_layout import image_on_white
from app.services.ocr_engine import normalize_reference
from app.services.replacement_rendering import _draw_replacement_text, _sample_background_color
from app.services.replacement_typography import (
    dominant_height,
    font_size_for_height,
    measure_character_height,
)
from app.services.text_geometry import _box_points

log = structlog.get_logger(__name__)
REPLACEMENT_BOTTOM_INSET = 3.0


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
    box_height = (
        hypot(points[3][0] - points[0][0], points[3][1] - points[0][1])
        + hypot(points[2][0] - points[1][0], points[2][1] - points[1][1])
    ) / 2
    bottom_inset_ratio = min(REPLACEMENT_BOTTOM_INSET / max(box_height, 1.0), 0.12)
    bottom_start = _interpolate_point(bottom_start, top_start, bottom_inset_ratio)
    bottom_end = _interpolate_point(bottom_end, top_end, bottom_inset_ratio)
    return [top_start, top_end, bottom_end, bottom_start]


def apply_replacements(
    source_image: Image.Image,
    lines: list[dict[str, object]],
    replacement_pairs: list[dict[str, str]],
    replacement_font_size: int | None = None,
) -> tuple[Image.Image, list[int], int | None]:
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
            if occurrence_index >= len(pair_indices):
                continue

            pair_index = pair_indices[occurrence_index]
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

    if replacement_draws and replacement_font_size is None:
        heights = [
            height for polygon, _, background in replacement_draws
            if (height := measure_character_height(canvas, polygon, background)) is not None
        ]
        if len(heights) < len(replacement_draws):
            log.warning(
                "replacement_glyph_measurements_missing",
                measured=len(heights), total=len(replacement_draws),
            )
        replacement_font_size = font_size_for_height(dominant_height(heights))

    for polygon, _, background_color in replacement_draws:
        draw.polygon(polygon, fill=background_color)
    for polygon, pair_index, _ in replacement_draws:
        if replacement_font_size is None:
            raise RuntimeError("Missing replacement typography.")
        _draw_replacement_text(
            canvas,
            polygon,
            replacement_pairs[pair_index]["replacement"],
            (0, 0, 0),
            font_size=replacement_font_size,
        )

    return canvas, applied_counts, replacement_font_size
