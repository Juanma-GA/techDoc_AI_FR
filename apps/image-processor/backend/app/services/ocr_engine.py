from __future__ import annotations

import json
import re
import unicodedata

from fastapi import HTTPException

from app.services.text_geometry import _to_list, reading_order_boxes


def normalize_reference(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", ascii_text.upper())


def _normalized_text_with_positions(value: str) -> tuple[str, list[int]]:
    normalized_parts: list[str] = []
    positions: list[int] = []
    for index, character in enumerate(value):
        normalized_character = normalize_reference(character)
        normalized_parts.append(normalized_character)
        positions.extend([index] * len(normalized_character))
    return "".join(normalized_parts), positions


def find_reference_occurrences(value: str, reference: str) -> list[tuple[int, int]]:
    normalized_reference = normalize_reference(reference)
    if not normalized_reference:
        return []

    normalized_text, positions = _normalized_text_with_positions(value)
    occurrences: list[tuple[int, int]] = []
    search_offset = 0
    while True:
        start = normalized_text.find(normalized_reference, search_offset)
        if start < 0:
            break
        end = start + len(normalized_reference)
        source_start = positions[start]
        source_end = positions[end - 1] + 1
        starts_inside_character = start > 0 and positions[start - 1] == source_start
        ends_inside_character = end < len(positions) and positions[end] == source_end - 1
        has_left_boundary = source_start == 0 or not normalize_reference(value[source_start - 1])
        has_right_boundary = source_end == len(value) or not normalize_reference(value[source_end])

        if (
            not starts_inside_character
            and not ends_inside_character
            and has_left_boundary
            and has_right_boundary
        ):
            occurrences.append((source_start, source_end))
            search_offset = end
        else:
            search_offset = start + 1
    return occurrences


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
    oriented_boxes = reading_order_boxes(
        [boxes[index] if index < len(boxes) else [] for index in range(len(texts))],
        data.get("dt_polys"), data.get("textline_orientation_angles"), texts,
    )

    lines: list[dict[str, object]] = []
    for index, text in enumerate(texts):
        if not isinstance(text, str):
            raise RuntimeError("PaddleOCR a renvoyé une ligne sans texte valide.")
        lines.append(
            {
                "text": text,
                "confidence": float(scores[index]),
                "box": oriented_boxes[index],
                "matched_references": [],
            }
        )
    return lines


def _match_references(
    lines: list[dict[str, object]], references: list[str]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
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

    for pair_indices in reference_indices.values():
        occurrences: list[list[int]] = []
        reference = references[pair_indices[0]]
        for line_index, line in enumerate(lines):
            occurrences.extend(
                [[line_index] for _ in find_reference_occurrences(str(line["text"]), reference)]
            )

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


def _parse_replacement_pairs(
    raw_pairs: str,
    *,
    skip_empty_references: bool = False,
    allow_empty_replacement: bool = False,
) -> list[dict[str, str]]:
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
        if skip_empty_references and not reference:
            continue
        normalized_reference = normalize_reference(reference)
        if not normalized_reference or (not replacement and not allow_empty_replacement):
            raise HTTPException(
                status_code=422,
                detail="Chaque couple doit contenir une référence et un nouveau repère.",
            )

        pairs.append({"reference": reference, "replacement": replacement})
    return pairs
