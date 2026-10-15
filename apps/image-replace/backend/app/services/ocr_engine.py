from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import requests
import truststore
from fastapi import HTTPException

from app.services.constants import OCR_DETECTION_MAX_SIDE

truststore.inject_into_ssl()

if TYPE_CHECKING:
    from paddleocr import PaddleOCR


@lru_cache(maxsize=1)
def get_ocr_engine() -> PaddleOCR:
    from paddleocr import PaddleOCR

    original_get = requests.get

    def get_with_model_download_timeout(url: str, *args: object, **kwargs: object):
        if kwargs.get("stream") is True and kwargs.get("timeout") == 15:
            kwargs["timeout"] = (15, 120)
        return original_get(url, *args, **kwargs)

    requests.get = get_with_model_download_timeout
    try:
        return PaddleOCR(
            lang="en",
            device="cpu",
            enable_mkldnn=False,
            text_det_limit_side_len=OCR_DETECTION_MAX_SIDE,
            text_det_limit_type="max",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    finally:
        requests.get = original_get


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

    matches: list[dict[str, object]] = []
    line_matches: list[list[str]] = [[] for _ in lines]
    for reference in references:
        normalized = normalize_reference(reference)
        found_lines: set[int] = set()
        start = normalized_text.find(normalized)
        while start >= 0:
            found_lines.update(character_lines[start : start + len(normalized)])
            start = normalized_text.find(normalized, start + len(normalized))

        indices = sorted(found_lines)
        for index in indices:
            line_matches[index].append(reference)
        matches.append({"reference": reference, "found": bool(indices), "line_indices": indices})

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
    seen_references: set[str] = set()
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
        if normalized_reference in seen_references:
            raise HTTPException(
                status_code=422,
                detail="Une même référence ne peut pas apparaître plusieurs fois.",
            )

        seen_references.add(normalized_reference)
        pairs.append({"reference": reference, "replacement": replacement})
    return pairs


def run_ocr_on_image(image_bytes: bytes) -> object:
    with TemporaryDirectory() as temporary_directory:
        image_path = Path(temporary_directory) / "image.png"
        image_path.write_bytes(image_bytes)
        predictions = iter(get_ocr_engine().predict(input=str(image_path)))
        prediction = next(predictions, None)
        if prediction is None:
            raise RuntimeError("PaddleOCR n'a renvoyé aucun résultat pour cette image.")
        return prediction
