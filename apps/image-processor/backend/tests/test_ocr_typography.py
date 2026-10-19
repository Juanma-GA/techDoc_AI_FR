from __future__ import annotations

import base64
import json
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image, ImageChops

from app.services.constants import A4_HEIGHT, A4_WIDTH, MAX_REPLACEMENT_FONT_SIZE

BASE = "/api/v1/image-replace/ocr"


def _prediction(texts, boxes):
    return SimpleNamespace(json={"res": {
        "rec_texts": texts, "rec_scores": [0.99] * len(texts), "rec_polys": boxes,
    }})


def test_a4_font_size_is_reused_when_rerunning_on_another_reference(client, monkeypatch, typography_sample):
    source = Image.new("RGB", (1200, 300), "white")
    boxes = []
    for index, size in enumerate([24, 48, 24]):
        image, polygon, _ = typography_sample(text=f"R{index + 1}", size=size)
        source.paste(image, (400 * index, 0))
        boxes.append([[x + 400 * index, y] for x, y in polygon])
    encoded = BytesIO()
    source.save(encoded, format="PNG")
    monkeypatch.setattr(
        "app.api.ocr.run_ocr_on_image",
        lambda image_bytes, timings=None: _prediction(["R1", "R2", "R3"], boxes),
    )
    first = client.post(
        BASE, files={"image": ("synthetic.png", encoded.getvalue(), "image/png")},
        data={"replacement_pairs": json.dumps([
            {"reference": "R1", "replacement": "101"}, {"reference": "R3", "replacement": "103"},
        ])},
    )
    assert first.status_code == 200, first.text
    initial = first.json()
    font_size = initial["replacement_font_size"]
    assert isinstance(font_size, int) and font_size > 24
    first_image = base64.b64decode(initial["edited_image"].split(",")[1])
    a4_boxes = [line["box"] for line in initial["lines"]]
    monkeypatch.setattr(
        "app.api.ocr.run_ocr_on_image",
        lambda image_bytes, timings=None: _prediction(["101", "R2", "103"], a4_boxes),
    )
    second = client.post(
        BASE, files={"image": ("synthetic.png", first_image, "image/jpeg")},
        data={
            "replacement_pairs": '[{"reference":"R2","replacement":"102"}]',
            "replacement_font_size": str(font_size),
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["replacement_font_size"] == font_size
    result_bytes = base64.b64decode(second.json()["edited_image"].split(",")[1])
    with Image.open(BytesIO(result_bytes)) as result:
        assert result.size == (A4_WIDTH, A4_HEIGHT)
        heights = []
        for polygon in a4_boxes:
            left = round(min(x for x, _ in polygon))
            right = round(max(x for x, _ in polygon))
            tile = result.crop((left, 0, right, A4_HEIGHT)).convert("RGB")
            ink = ImageChops.difference(tile, Image.new("RGB", tile.size, "white")).convert("L")
            bounds = ink.point([255 if value >= 128 else 0 for value in range(256)]).getbbox()
            assert bounds is not None
            heights.append(bounds[3] - bounds[1])
        assert max(heights) - min(heights) <= 1


@pytest.mark.parametrize("font_size", ["0", "-1", "24.5", str(MAX_REPLACEMENT_FONT_SIZE + 1)])
def test_invalid_persisted_font_size_is_rejected_before_inference(client, font_size):
    response = client.post(BASE, files={"image": ("synthetic.png", b"unused")}, data={
        "replacement_font_size": font_size,
    })
    assert response.status_code == 422


@pytest.mark.parametrize("font_size", [None, 36])
def test_history_keeps_font_metadata_and_accepts_older_analysis(
    workspace_client, workspace_state, font_size,
):
    analysis = {
        "width": 20, "height": 30, "source_width": 20, "source_height": 30,
        "full_text": "", "lines": [], "references": [], "filename": "ICN-TEST.jpg",
    }
    if font_size is not None:
        analysis["replacement_font_size"] = font_size
    workspace_state["revisions"][0]["analysis"] = analysis
    entry_id = str(uuid4())
    response = workspace_client.put(f"/api/v1/image-replace/history/{entry_id}", json=workspace_state)
    assert response.status_code == 200
    restored = workspace_client.get(f"/api/v1/image-replace/history/{entry_id}").json()
    assert restored["state"]["revisions"][0]["analysis"]["replacement_font_size"] == font_size
