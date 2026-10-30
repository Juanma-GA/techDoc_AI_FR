from __future__ import annotations

import base64
import json
from io import BytesIO

import structlog
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
    line = {
        "text": "R-001",
        "box": [[110, 120], [210, 120], [210, 150], [110, 150]],
    }
    empty_line = {"text": "", "box": [[110, 160], [210, 160], [210, 190], [110, 190]]}
    response = client.post(
        "/api/v1/image-processor/reapply-replacements",
        files={"image": ("source.jpg", _source_jpeg(), "image/jpeg")},
        data={
            "lines_json": json.dumps([empty_line, line]),
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
    assert payload["partial_line_indices"] == [[]]
    assert payload["replacement_font_size"] == 14
    assert captured == {
        "size": (A4_WIDTH, A4_HEIGHT),
        "lines": [{
            "text": "R-001",
            "box": line["box"],
            "matched_references": ["R-001"],
        }],
        "pairs": [{"reference": "R-001", "replacement": "R-002"}],
        "font_size": 12,
        "broadcast_references": {"R001"},
    }

    image_bytes = base64.b64decode(payload["edited_image"].split(",", 1)[1])
    with Image.open(BytesIO(image_bytes)) as rendered:
        assert rendered.size == (A4_WIDTH, A4_HEIGHT)
        assert rendered.info["dpi"] == (A4_DPI, A4_DPI)


def test_reapply_replacements_recomputes_stale_ocr_matches(client: TestClient, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_apply_replacements(image, lines, pairs, font_size, broadcast_references):
        captured.update(lines=lines, pairs=pairs)
        return image.copy(), [1], 14

    monkeypatch.setattr("app.api.line_replacement.apply_replacements", fake_apply_replacements)
    lines = [
        {
            "text": "34 708 SM",
            "box": [[100, 100], [210, 100], [210, 130], [100, 130]],
            "matched_references": [],
        },
        {
            "text": "34 708 SM 2",
            "box": [[100, 140], [230, 140], [230, 170], [100, 170]],
            "matched_references": ["34708SM"],
        },
    ]
    response = client.post(
        "/api/v1/image-processor/reapply-replacements",
        files={"image": ("source.jpg", _source_jpeg(), "image/jpeg")},
        data={
            "lines_json": json.dumps(lines),
            "replacement_pairs_json": json.dumps([
                {"reference": "34708SM", "replacement": "28"},
            ]),
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["replacement_counts"] == [1]
    assert response.json()["partial_line_indices"] == [[1]]
    assert captured == {
        "lines": [
            {
                "text": "34 708 SM",
                "box": lines[0]["box"],
                "matched_references": ["34708SM"],
            },
            {
                "text": "34 708 SM 2",
                "box": lines[1]["box"],
                "matched_references": [],
            },
        ],
        "pairs": [{"reference": "34708SM", "replacement": "28"}],
    }


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


def test_reapply_replacements_logs_safe_validation_details(client: TestClient) -> None:
    private_ocr_text = "PRIVATE OCR TEXT"
    with structlog.testing.capture_logs() as logs:
        response = client.post(
            "/api/v1/image-processor/reapply-replacements",
            files={"image": ("source.jpg", _source_jpeg(), "image/jpeg")},
            data={
                "lines_json": json.dumps([{
                    "text": private_ocr_text,
                    "box": [[110, 120], [210, 120], [210, 150]],
                }]),
                "replacement_pairs_json": json.dumps([
                    {"reference": "R-001", "replacement": "R-002"},
                ]),
            },
        )

    assert response.status_code == 422
    event = next(log for log in logs if log["event"] == "reapply_replacements_payload_invalid")
    assert event["field"] == "lines_json"
    assert event["validation_errors"]
    assert private_ocr_text not in repr(event)


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
