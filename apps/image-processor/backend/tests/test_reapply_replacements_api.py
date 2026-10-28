from __future__ import annotations

import base64
import json
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.services.constants import A4_DPI, A4_HEIGHT, A4_WIDTH
from app.workspace_schemas import OcrLine


def _source_jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white").save(output, format="JPEG")
    return output.getvalue()


def test_reapply_replacements_uses_shifted_boxes_and_original_source(
    client: TestClient, monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_apply_replacements(image, lines, pairs, font_size, broadcast_references):
        captured.update(
            size=image.size,
            lines=lines,
            pairs=pairs,
            font_size=font_size,
            broadcast_references=broadcast_references,
        )
        return image.copy(), [2], 14

    monkeypatch.setattr("app.api.line_replacement.apply_replacements", fake_apply_replacements)
    line = {"text": "R-001", "box": [[110, 120], [210, 120], [210, 150], [110, 150]]}
    response = client.post(
        "/api/v1/image-processor/reapply-replacements",
        files={"image": ("source.jpg", _source_jpeg(), "image/jpeg")},
        data={
            "lines_json": json.dumps([line]),
            "replacement_pairs_json": json.dumps([
                {"reference": "R-001", "replacement": "R-002"},
            ]),
            "broadcast_references_json": json.dumps(["r001"]),
            "replacement_font_size": "12",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["replacement_counts"] == [2]
    assert payload["replacement_font_size"] == 14
    assert captured == {
        "size": (A4_WIDTH, A4_HEIGHT),
        "lines": [{"text": "R-001", "box": line["box"]}],
        "pairs": [{"reference": "R-001", "replacement": "R-002"}],
        "font_size": 12,
        "broadcast_references": {"R001"},
    }

    image_bytes = base64.b64decode(payload["edited_image"].split(",", 1)[1])
    with Image.open(BytesIO(image_bytes)) as rendered:
        assert rendered.size == (A4_WIDTH, A4_HEIGHT)
        assert rendered.info["dpi"] == (A4_DPI, A4_DPI)


def test_reapply_replacements_rejects_boxes_outside_a4(client: TestClient) -> None:
    response = client.post(
        "/api/v1/image-processor/reapply-replacements",
        files={"image": ("source.jpg", _source_jpeg(), "image/jpeg")},
        data={
            "lines_json": json.dumps([{
                "text": "R-001",
                "box": [[-1, 120], [210, 120], [210, 150], [110, 150]],
            }]),
            "replacement_pairs_json": json.dumps([
                {"reference": "R-001", "replacement": "R-002"},
            ]),
        },
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Une boîte OCR est hors de l'image."


def test_workspace_ocr_line_persists_box_offset() -> None:
    line = OcrLine.model_validate({
        "text": "R-001",
        "confidence": 1,
        "box": [[110, 120], [210, 120], [210, 150], [110, 150]],
        "original_box": [[100, 100], [200, 100], [200, 130], [100, 130]],
        "box_offset_x": 10,
        "box_offset_y": 20,
        "matched_references": ["R-001"],
    })

    assert line.box_offset_x == 10
    assert line.box_offset_y == 20
    assert line.original_box is not None
    assert line.original_box[0] == [100, 100]
