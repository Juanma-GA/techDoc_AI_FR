"""Reading-order quadrilaterals and text-local geometry in image coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot, isfinite

from fastapi import HTTPException


def _to_list(value: object) -> list[object]:
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        value = tolist()
    return value if isinstance(value, list) else []


def _box_points(value: object) -> list[list[float]]:
    coordinates = _to_list(value)
    if len(coordinates) == 4 and all(isinstance(item, (int, float)) for item in coordinates):
        x1, y1, x2, y2 = (float(item) for item in coordinates)
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    points: list[list[float]] = []
    for point in coordinates:
        pair = _to_list(point)
        if len(pair) < 2:
            return []
        points.append([float(pair[0]), float(pair[1])])
    return points


@dataclass(frozen=True)
class TextFrame:
    center: tuple[float, float]
    width: float
    height: float
    angle: float


def text_frame(points: list[list[float]]) -> TextFrame:
    if len(points) != 4 or any(not isfinite(value) for point in points for value in point):
        raise HTTPException(status_code=422, detail="La geometrie du texte OCR est invalide.")
    top = (points[1][0] - points[0][0], points[1][1] - points[0][1])
    bottom = (points[2][0] - points[3][0], points[2][1] - points[3][1])
    width = (hypot(*top) + hypot(*bottom)) / 2
    height = (
        hypot(points[3][0] - points[0][0], points[3][1] - points[0][1])
        + hypot(points[2][0] - points[1][0], points[2][1] - points[1][1])
    ) / 2
    if width < 1 or height < 1:
        raise HTTPException(status_code=422, detail="La zone du texte OCR est trop petite.")
    return TextFrame(
        center=(sum(point[0] for point in points) / 4, sum(point[1] for point in points) / 4),
        width=width, height=height,
        angle=degrees(atan2(top[1] + bottom[1], top[0] + bottom[0])),
    )


def reading_order_box(
    box: object, orientation: object = -1, text_length: int | None = None,
) -> list[list[float]]:
    points = _box_points(box)
    if len(points) != 4:
        return points
    text_frame(points)
    crop_width = int(max(
        hypot(points[1][0] - points[0][0], points[1][1] - points[0][1]),
        hypot(points[2][0] - points[3][0], points[2][1] - points[3][1]),
    ))
    crop_height = int(max(
        hypot(points[3][0] - points[0][0], points[3][1] - points[0][1]),
        hypot(points[2][0] - points[1][0], points[2][1] - points[1][1]),
    ))
    # Paddle rotates tall crops 90 degrees before its 0/180-degree classifier.
    # A narrow single glyph such as "1" is not evidence of a vertical baseline.
    if crop_height / crop_width >= 1.5 and (text_length is None or text_length > 1):
        points = points[1:] + points[:1]
    # Installed PaddleX exposes class IDs 0/1; other versions expose degrees.
    if orientation in (1, 180):
        points = points[2:] + points[:2]
    elif orientation not in (-1, 0):
        raise RuntimeError("PaddleOCR a renvoye une orientation de texte inattendue.")
    return points


def reading_order_boxes(
    boxes: list[object], detections: object, orientations: object, texts: list[object] | None = None,
) -> list[list[list[float]]]:
    lengths = [
        sum(character.isalnum() for character in text) if isinstance(text, str) else None
        for text in texts
    ] if texts is not None else [None] * len(boxes)
    angles = _to_list(orientations)
    if not angles:
        return [reading_order_box(box, text_length=lengths[index]) for index, box in enumerate(boxes)]
    detected = _to_list(detections)
    if not detected:
        if len(angles) != len(boxes):
            raise RuntimeError("PaddleOCR a renvoye des orientations incompatibles.")
        return [
            reading_order_box(box, angle, lengths[index])
            for index, (box, angle) in enumerate(zip(boxes, angles, strict=True))
        ]
    if len(angles) != len(detected):
        raise RuntimeError("PaddleOCR a renvoye des orientations incompatibles.")

    def key(box: object) -> tuple[tuple[float, ...], ...]:
        return tuple(tuple(point) for point in _box_points(box))

    # Orientation IDs precede recognition-score filtering in PaddleX.
    by_polygon = {key(box): angle for box, angle in zip(detected, angles, strict=True)}
    result: list[list[list[float]]] = []
    for index, box in enumerate(boxes):
        if key(box) not in by_polygon:
            raise RuntimeError("L'orientation d'une ligne OCR est manquante.")
        result.append(reading_order_box(box, by_polygon[key(box)], lengths[index]))
    return result


def snapped_angle(angle: float) -> float:
    nearest_axis = round(angle / 90) * 90
    return float(nearest_axis) if abs(angle - nearest_axis) <= 10 else angle
