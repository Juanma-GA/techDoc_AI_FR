from __future__ import annotations

from typing import Any, Literal

from app.core.ocr_types import OcrBox


def extract_result(
    payload: Any,
    image_width: int,
    image_height: int,
    *,
    coordinate_mode: Literal["auto", "pixels"] = "auto",
) -> tuple[str, list[OcrBox]]:
    boxes: list[OcrBox] = []
    text_parts: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            raw_text = node.get("text") or node.get("markdown") or node.get("content")
            raw_box = node.get("bbox") or node.get("box") or node.get("polygon")
            if raw_box is None and all(
                isinstance(node.get(key), (int, float))
                for key in ("top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y")
            ):
                raw_box = [
                    node["top_left_x"],
                    node["top_left_y"],
                    node["bottom_right_x"],
                    node["bottom_right_y"],
                ]
            recognition_texts = node.get("rec_texts")
            recognition_boxes = node.get("rec_boxes") or node.get("rec_polys")
            recognition_scores = node.get("rec_scores")
            if isinstance(recognition_texts, list) and isinstance(recognition_boxes, list):
                for index, recognition_text in enumerate(recognition_texts):
                    if not isinstance(recognition_text, str) or not recognition_text.strip():
                        continue
                    score = (
                        recognition_scores[index]
                        if isinstance(recognition_scores, list) and index < len(recognition_scores)
                        else None
                    )
                    box = normalized_box(
                        recognition_boxes[index]
                        if index < len(recognition_boxes)
                        else None,
                        recognition_text.strip(),
                        score,
                        image_width,
                        image_height,
                        coordinate_mode,
                    )
                    if box is not None:
                        boxes.append(box)
                    text_parts.append(recognition_text.strip())
                skipped_keys = {"rec_texts", "rec_boxes", "rec_polys", "rec_scores"}
            else:
                lines = node.get("lines")
                blocks = node.get("blocks")
                structured_items = (
                    lines
                    if _has_text_items(lines)
                    else blocks
                    if _has_text_items(blocks)
                    else None
                )
                if isinstance(raw_text, str) and raw_text.strip():
                    confidence = node.get("confidence", node.get("score", node.get("conf")))
                    confidence_scores = node.get("confidence_scores")
                    if confidence is None and isinstance(confidence_scores, dict):
                        confidence = confidence_scores.get("average_content_confidence_score")
                    if raw_box is not None:
                        box = normalized_box(
                            raw_box,
                            raw_text.strip(),
                            confidence,
                            image_width,
                            image_height,
                            coordinate_mode,
                        )
                        if box is not None:
                            boxes.append(box)
                    if raw_box is not None or structured_items is None:
                        text_parts.append(raw_text.strip())
                skipped_keys = set()
                if structured_items is not None:
                    skipped_keys.add("markdown")
                    if structured_items is lines:
                        skipped_keys.add("blocks")
            for key, value in node.items():
                if key not in {
                    "text",
                    "content",
                    "markdown",
                    "type",
                    "bbox",
                    "box",
                    "polygon",
                    "confidence",
                    "score",
                    "conf",
                    *skipped_keys,
                }:
                    visit(value)
        elif isinstance(node, list):
            if (
                len(node) >= 2
                and isinstance(node[0], (list, tuple))
                and isinstance(node[1], (list, tuple))
                and node[1]
                and isinstance(node[1][0], str)
            ):
                box = normalized_box(
                    node[0],
                    node[1][0],
                    node[1][1] if len(node[1]) > 1 else None,
                    image_width,
                    image_height,
                    coordinate_mode,
                )
                if box is not None:
                    boxes.append(box)
                text_parts.append(node[1][0].strip())
                return
            for item in node:
                visit(item)
        elif isinstance(node, str) and node.strip():
            text_parts.append(node.strip())

    visit(payload)
    return "\n".join(text_parts), boxes


def _has_text_items(value: Any) -> bool:
    return isinstance(value, list) and any(
        isinstance(item, dict)
        and isinstance(item.get("text") or item.get("content"), str)
        and (item.get("text") or item.get("content")).strip()
        for item in value
    )


def normalized_box(
    raw: Any,
    text: str,
    confidence: Any,
    image_width: int,
    image_height: int,
    coordinate_mode: Literal["auto", "pixels"] = "auto",
) -> OcrBox | None:
    try:
        if (
            isinstance(raw, (list, tuple))
            and len(raw) == 4
            and all(isinstance(value, (int, float)) for value in raw)
        ):
            x0, y0, x1, y1 = (float(value) for value in raw)
        elif isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], (list, tuple)):
            points = [(float(point[0]), float(point[1])) for point in raw if len(point) >= 2]
            if len(points) < 2:
                return None
            x0 = min(point[0] for point in points)
            y0 = min(point[1] for point in points)
            x1 = max(point[0] for point in points)
            y1 = max(point[1] for point in points)
        else:
            return None
    except (TypeError, ValueError):
        return None

    if image_width <= 0 or image_height <= 0:
        return None
    if coordinate_mode == "pixels":
        x0, x1 = x0 / image_width, x1 / image_width
        y0, y1 = y0 / image_height, y1 / image_height
    elif max(abs(x0), abs(x1)) <= 1 and max(abs(y0), abs(y1)) <= 1:
        pass
    elif max(abs(x0), abs(x1)) <= 1000 and max(abs(y0), abs(y1)) <= 1000:
        x0, x1 = x0 / 1000, x1 / 1000
        y0, y1 = y0 / 1000, y1 / 1000
    else:
        x0, x1 = x0 / image_width, x1 / image_width
        y0, y1 = y0 / image_height, y1 / image_height
    if x1 <= x0 or y1 <= y0:
        return None
    try:
        score = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        score = None
    return OcrBox(
        x0=max(0, min(x0, 1)),
        y0=max(0, min(y0, 1)),
        x1=max(0, min(x1, 1)),
        y1=max(0, min(y1, 1)),
        text=text,
        confidence=score,
    )
