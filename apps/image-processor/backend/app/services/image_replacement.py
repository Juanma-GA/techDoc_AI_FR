from __future__ import annotations

from math import ceil, floor, hypot
from typing import TypedDict

import structlog
from PIL import Image, ImageChops, ImageDraw

from app.services.image_layout import image_on_white
from app.services.ocr_engine import normalize_reference
from app.services.replacement_rendering import _draw_replacement_text, _sample_background_color
from app.services.replacement_typography import (
    dominant_height,
    font_size_for_height,
    measure_character_bounds,
)
from app.services.text_geometry import _box_points, text_frame

log = structlog.get_logger(__name__)
REPLACEMENT_SIDE_INSET = 1.5
REPLACEMENT_TOP_INSET = 1.0
REPLACEMENT_BOTTOM_INSET = 6.5
REPLACEMENT_EDGE_INSET_RATIO_CAP = 0.12
REPLACEMENT_BOTTOM_INSET_RATIO_CAP = 0.3
REPLACEMENT_CORNER_RADIUS = 3.0
REPLACEMENT_MASK_SUPERSAMPLE = 4
REPLACEMENT_VISIBLE_INK_TOP_PADDING = 3.0
REPLACEMENT_VISIBLE_INK_BOTTOM_PADDING = 1.0


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


def _round_polygon_corners(
    polygon: list[list[float]], radius: float,
) -> list[list[float]]:
    if len(polygon) < 3 or radius <= 0:
        return polygon

    rounded: list[list[float]] = []
    curve_steps = 4
    for index, vertex in enumerate(polygon):
        previous = polygon[index - 1]
        following = polygon[(index + 1) % len(polygon)]
        previous_length = hypot(vertex[0] - previous[0], vertex[1] - previous[1])
        following_length = hypot(following[0] - vertex[0], following[1] - vertex[1])
        if previous_length == 0 or following_length == 0:
            rounded.append(vertex)
            continue

        corner_radius = min(radius, previous_length / 2, following_length / 2)
        curve_start = _interpolate_point(
            vertex, previous, corner_radius / previous_length,
        )
        curve_end = _interpolate_point(
            vertex, following, corner_radius / following_length,
        )
        for step in range(curve_steps + 1):
            ratio = step / curve_steps
            inverse = 1 - ratio
            rounded.append(
                [
                    inverse**2 * curve_start[axis]
                    + 2 * inverse * ratio * vertex[axis]
                    + ratio**2 * curve_end[axis]
                    for axis in range(2)
                ]
            )
    return rounded


def _draw_replacement_mask(
    image: Image.Image,
    polygon: list[list[float]],
    fill: tuple[int, int, int],
    protected_strokes: list[list[list[float]]],
) -> None:
    left = max(0, floor(min(point[0] for point in polygon)))
    top = max(0, floor(min(point[1] for point in polygon)))
    right = min(image.width, ceil(max(point[0] for point in polygon)) + 1)
    bottom = min(image.height, ceil(max(point[1] for point in polygon)) + 1)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        return

    scale = REPLACEMENT_MASK_SUPERSAMPLE
    mask = Image.new("L", (width * scale, height * scale), 0)
    scaled_polygon = [
        ((point[0] - left) * scale, (point[1] - top) * scale)
        for point in polygon
    ]
    ImageDraw.Draw(mask).polygon(scaled_polygon, fill=255)
    mask = mask.resize((width, height), Image.Resampling.LANCZOS)
    mask = mask.point(lambda coverage: 255 if coverage >= 128 else 0)
    mask_draw = ImageDraw.Draw(mask)
    for stroke in protected_strokes:
        local_stroke = [(point[0] - left, point[1] - top) for point in stroke]
        mask_draw.polygon(local_stroke, fill=0)
    fill_image = Image.new("RGB", mask.size, fill)
    image.paste(fill_image, (left, top), mask)


def _replacement_segment(
    box: object, text_length: int, start_index: int, end_index: int
) -> list[list[float]]:
    points = _box_points(box)
    if len(points) < 4 or text_length <= 0:
        return []

    start_ratio = start_index / text_length
    end_ratio = end_index / text_length
    box_width = (
        hypot(points[1][0] - points[0][0], points[1][1] - points[0][1])
        + hypot(points[2][0] - points[3][0], points[2][1] - points[3][1])
    ) / 2
    side_inset_ratio = min(
        REPLACEMENT_SIDE_INSET / max(box_width, 1.0),
        (end_ratio - start_ratio) / 4,
        REPLACEMENT_EDGE_INSET_RATIO_CAP,
    )
    start_ratio += side_inset_ratio
    end_ratio -= side_inset_ratio
    if start_ratio >= end_ratio:
        return []

    top_start = _interpolate_point(points[0], points[1], start_ratio)
    top_end = _interpolate_point(points[0], points[1], end_ratio)
    bottom_end = _interpolate_point(points[3], points[2], end_ratio)
    bottom_start = _interpolate_point(points[3], points[2], start_ratio)
    return [top_start, top_end, bottom_end, bottom_start]


def _fit_segment_to_visible_ink(
    polygon: list[list[float]], bounds: tuple[int, int] | None,
) -> list[list[float]]:
    frame = text_frame(polygon)
    crop_height = max(1, ceil(frame.height))
    if bounds is None:
        top_ratio = min(
            REPLACEMENT_TOP_INSET / max(frame.height, 1.0),
            REPLACEMENT_EDGE_INSET_RATIO_CAP,
        )
        bottom_ratio = 1 - min(
            REPLACEMENT_BOTTOM_INSET / max(frame.height, 1.0),
            REPLACEMENT_BOTTOM_INSET_RATIO_CAP,
        )
    else:
        top_ratio = max(
            0.0,
            (bounds[0] - REPLACEMENT_VISIBLE_INK_TOP_PADDING) / crop_height,
        )
        bottom_ratio = min(
            1.0,
            (bounds[1] + REPLACEMENT_VISIBLE_INK_BOTTOM_PADDING) / crop_height,
        )

    top_left = _interpolate_point(polygon[0], polygon[3], top_ratio)
    top_right = _interpolate_point(polygon[1], polygon[2], top_ratio)
    bottom_right = _interpolate_point(polygon[1], polygon[2], bottom_ratio)
    bottom_left = _interpolate_point(polygon[0], polygon[3], bottom_ratio)
    return [top_left, top_right, bottom_right, bottom_left]


def _map_text_point_to_image(
    polygon: list[list[float]], x: float, y: float, width: int, height: int,
) -> list[float]:
    x_ratio = min(1.0, max(0.0, x / width))
    y_ratio = min(1.0, max(0.0, y / height))
    top = _interpolate_point(polygon[0], polygon[1], x_ratio)
    bottom = _interpolate_point(polygon[3], polygon[2], x_ratio)
    return _interpolate_point(top, bottom, y_ratio)


def _detect_horizontal_strokes(
    image: Image.Image,
    polygon: list[list[float]],
    bounds: tuple[int, int] | None,
    background: tuple[int, int, int],
) -> list[list[list[float]]]:
    frame = text_frame(polygon)
    width, height = max(1, ceil(frame.width)), max(1, ceil(frame.height))
    coordinates = tuple(value for index in (0, 3, 2, 1) for value in polygon[index])
    crop = image.transform(
        (width, height), Image.Transform.QUAD, coordinates, Image.Resampling.BICUBIC,
        fillcolor=background,
    )
    difference = ImageChops.difference(
        crop, Image.new("RGB", (width, height), background),
    ).convert("L")
    contrast = difference.getextrema()[1]
    if contrast < 24:
        return []

    threshold = max(24, ceil(contrast * 0.25))
    minimum_run = max(5, ceil(width * 0.45))
    search_start = (
        max(0, bounds[1] - max(2, ceil(height * 0.08)))
        if bounds is not None
        else int(height * 0.55)
    )
    strokes: list[list[list[float]]] = []
    for y in range(search_start, height):
        x = 0
        while x < width:
            if difference.getpixel((x, y)) < threshold:
                x += 1
                continue

            start = x
            while x < width and difference.getpixel((x, y)) >= threshold:
                x += 1
            if x - start < minimum_run:
                continue

            left, right = start - 0.5, x - 0.5
            top, bottom = y - 0.5, y + 0.5
            strokes.append(
                [
                    _map_text_point_to_image(polygon, left, top, width, height),
                    _map_text_point_to_image(polygon, right, top, width, height),
                    _map_text_point_to_image(polygon, right, bottom, width, height),
                    _map_text_point_to_image(polygon, left, bottom, width, height),
                ]
            )
    return strokes


def apply_replacements(
    source_image: Image.Image,
    lines: list[dict[str, object]],
    replacement_pairs: list[dict[str, str]],
    replacement_font_size: int | None = None,
    broadcast_references: set[str] | None = None,
) -> tuple[Image.Image, list[int], int | None]:
    broadcast_references = broadcast_references or set()
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
        if reference in broadcast_references and len(pair_indices) == 1:
            pair_index = pair_indices[0]
            for occurrence in reference_occurrences:
                occurrence["pair_index"] = pair_index
                accepted.append(occurrence)
                applied_counts[pair_index] += 1
            continue

        for occurrence_index, occurrence in enumerate(reference_occurrences):
            if occurrence_index >= len(pair_indices):
                continue

            pair_index = pair_indices[occurrence_index]
            occurrence["pair_index"] = pair_index
            accepted.append(occurrence)
            applied_counts[pair_index] += 1

    accepted.sort(key=lambda item: (item["line_index"], item["start"]))
    canvas = image_on_white(source_image)
    replacement_draws: list[
        tuple[
            list[list[float]],
            list[list[float]],
            int,
            tuple[int, int, int],
            float | None,
            list[list[list[float]]],
        ]
    ] = []
    for occurrence in accepted:
        candidate_polygon = occurrence["polygon"]
        background = _sample_background_color(canvas, candidate_polygon)
        character_bounds = measure_character_bounds(canvas, candidate_polygon, background)
        text_polygon = _fit_segment_to_visible_ink(candidate_polygon, character_bounds)
        mask_polygon = _round_polygon_corners(text_polygon, REPLACEMENT_CORNER_RADIUS)
        protected_strokes = _detect_horizontal_strokes(
            canvas, candidate_polygon, character_bounds, background,
        )
        replacement_draws.append(
            (
                text_polygon,
                mask_polygon,
                occurrence["pair_index"],
                background,
                (
                    float(character_bounds[1] - character_bounds[0])
                    if character_bounds is not None else None
                ),
                protected_strokes,
            )
        )

    if replacement_draws and replacement_font_size is None:
        heights = [
            height for _, _, _, _, height, _ in replacement_draws
            if height is not None
        ]
        if len(heights) < len(replacement_draws):
            log.warning(
                "replacement_glyph_measurements_missing",
                measured=len(heights), total=len(replacement_draws),
            )
        replacement_font_size = font_size_for_height(dominant_height(heights))

    for _, mask_polygon, _, background_color, _, protected_strokes in replacement_draws:
        _draw_replacement_mask(canvas, mask_polygon, background_color, protected_strokes)
    for text_polygon, _, pair_index, _, _, _ in replacement_draws:
        if replacement_font_size is None:
            raise RuntimeError("Missing replacement typography.")
        _draw_replacement_text(
            canvas,
            text_polygon,
            replacement_pairs[pair_index]["replacement"],
            (0, 0, 0),
            font_size=replacement_font_size,
        )

    return canvas, applied_counts, replacement_font_size
