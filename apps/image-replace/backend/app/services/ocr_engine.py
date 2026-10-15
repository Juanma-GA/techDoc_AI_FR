from __future__ import annotations

import json
import re
import unicodedata

from fastapi import HTTPException


def normalize_reference(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", ascii_text.upper())


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
        point_coordinates = _to_list(point)
        if len(point_coordinates) < 2:
            return []
        points.append([float(point_coordinates[0]), float(point_coordinates[1])])
    return points


def _build_lines(prediction: object) -> list[dict[str, object]]:
    prediction_json = getattr(prediction, "json", None)
    if not isinstance(prediction_json, dict):
        raise RuntimeError("PaddleOCR a renvoyé un résultat inattendu.")

    data = prediction_json.get("res", prediction_json)
    if not isinstance(data, dict):
        raise RuntimeError("Les données OCR sont dans un format inattendu.")

    texts = _to_list(data.get("rec_texts"))
    scores = _to_list(data.get("rec_scores"))
    boxes = _to_list(data.get("rec_polys"))
    if not boxes:
        boxes = _to_list(data.get("rec_boxes"))
    if len(texts) != len(scores):
        raise RuntimeError("PaddleOCR a renvoyé des textes et scores incompatibles.")

    lines: list[dict[str, object]] = []
    for index, text in enumerate(texts):
        if not isinstance(text, str):
            raise RuntimeError("PaddleOCR a renvoyé une ligne sans texte valide.")
        lines.append(
            {
                "text": text,
                "confidence": float(scores[index]),
                "box": _box_points(boxes[index]) if index < len(boxes) else [],
                "matched_references": [],
            }
        )
    return lines


def _match_references(
    lines: list[dict[str, object]], references: list[str]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    normalized_text = ""
    character_lines: list[int] = []
    for index, line in enumerate(lines):
        normalized_line = normalize_reference(str(line["text"]))
        normalized_text += normalized_line
        character_lines.extend([index] * len(normalized_line))

    reference_indices: dict[str, list[int]] = {}
    matches: list[dict[str, object]] = [
        {"reference": reference, "found": False, "line_indices": []}
        for reference in references
    ]
    line_matches: list[list[str]] = [[] for _ in lines]
    for reference_index, reference in enumerate(references):
        normalized = normalize_reference(reference)
        if normalized:
            reference_indices.setdefault(normalized, []).append(reference_index)

    for normalized, pair_indices in reference_indices.items():
        occurrences: list[list[int]] = []
        start = normalized_text.find(normalized)
        while start >= 0:
            occurrences.append(
                sorted(set(character_lines[start : start + len(normalized)]))
            )
            start = normalized_text.find(normalized, start + len(normalized))

        for line_indices in occurrences:
            for line_index in line_indices:
                for pair_index in pair_indices:
                    reference = references[pair_index]
                    if reference not in line_matches[line_index]:
                        line_matches[line_index].append(reference)

        if len(pair_indices) == 1:
            pair_index = pair_indices[0]
            line_indices = sorted({index for occurrence in occurrences for index in occurrence})
            matches[pair_index] = {
                "reference": references[pair_index],
                "found": bool(occurrences),
                "line_indices": line_indices,
            }
            continue

        for occurrence_index, pair_index in enumerate(pair_indices):
            line_indices = (
                occurrences[occurrence_index]
                if occurrence_index < len(occurrences)
                else []
            )
            matches[pair_index] = {
                "reference": references[pair_index],
                "found": bool(line_indices),
                "line_indices": line_indices,
            }

    for index, values in enumerate(line_matches):
        lines[index]["matched_references"] = values
    return lines, matches


def _parse_replacement_pairs(raw_pairs: str) -> list[dict[str, str]]:
    try:
        payload = json.loads(raw_pairs)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="Les couples de remplacement sont invalides.") from error

    if not isinstance(payload, list):
        raise HTTPException(status_code=422, detail="Les couples de remplacement sont invalides.")

    pairs: list[dict[str, str]] = []
    for pair in payload:
        if not isinstance(pair, dict):
            raise HTTPException(
                status_code=422,
                detail="Chaque remplacement doit contenir une référence et un repère.",
            )

        reference = pair.get("reference")
        replacement = pair.get("replacement")
        if not isinstance(reference, str) or not isinstance(replacement, str):
            raise HTTPException(
                status_code=422,
                detail="Chaque remplacement doit contenir une référence et un repère.",
            )

        reference = reference.strip()
        replacement = replacement.strip()
        normalized_reference = normalize_reference(reference)
        if not normalized_reference or not replacement:
            raise HTTPException(
                status_code=422,
                detail="Chaque couple doit contenir une référence et un nouveau repère.",
            )

        pairs.append({"reference": reference, "replacement": replacement})
    return pairs
