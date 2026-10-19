from __future__ import annotations

import base64
import json
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.services.constants import A4_DPI, A4_HEIGHT, A4_WIDTH
from app.workspace_schemas import ImageRevision, Operation


def _a4_jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white").save(output, format="JPEG")
    return output.getvalue()


def test_workspace_accepts_text_replacement_revisions_and_operations() -> None:
    encoded_image = base64.b64encode(_a4_jpeg()).decode("ascii")
    revision = ImageRevision.model_validate({
        "image": {
            "name": "edited.jpg",
            "data_url": f"data:image/jpeg;base64,{encoded_image}",
        },
        "kind": "text-replacement",
    })
    operation = Operation.model_validate({
        "kind": "text-replacement",
        "at": "2026-10-19T10:00:00Z",
    })

    assert revision.kind == "text-replacement"
    assert operation.kind == "text-replacement"


def test_replace_line_renders_only_the_requested_ocr_line(
    client: TestClient, monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_apply_replacements(image, lines, pairs, replacement_font_size):
        captured.update(
            image_size=image.size,
            lines=lines,
            pairs=pairs,
            replacement_font_size=replacement_font_size,
        )
        rendered = image.copy()
        ImageDraw.Draw(rendered).rectangle((100, 100, 200, 130), fill="black")
        return rendered, [1], 12

    monkeypatch.setattr("app.api.line_replacement.apply_replacements", fake_apply_replacements)
    line = {
        "text": "K555",
        "box": [[100, 100], [200, 100], [200, 130], [100, 130]],
    }
    response = client.post(
        "/api/v1/image-processor/replace-line",
        files={"image": ("working.jpg", _a4_jpeg(), "image/jpeg")},
        data={
            "line_json": json.dumps(line),
            "reference": "K555",
            "replacement": "K777",
            "replacement_font_size": "10",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["replacement_count"] == 1
    assert payload["replacement_font_size"] == 12
    assert captured == {
        "image_size": (A4_WIDTH, A4_HEIGHT),
        "lines": [{"text": "K555", "box": line["box"]}],
        "pairs": [{"reference": "K555", "replacement": "K777"}],
        "replacement_font_size": 10,
    }

    image_bytes = base64.b64decode(payload["edited_image"].split(",", 1)[1])
    with Image.open(BytesIO(image_bytes)) as result:
        assert result.format == "JPEG"
        assert result.size == (A4_WIDTH, A4_HEIGHT)
        assert result.info["dpi"] == (A4_DPI, A4_DPI)


def test_replace_line_rejects_a_reference_not_present_in_the_selected_line(
    client: TestClient, monkeypatch,
) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("The renderer must not run for a reference absent from the OCR line.")

    monkeypatch.setattr("app.api.line_replacement.apply_replacements", fail_if_called)
    response = client.post(
        "/api/v1/image-processor/replace-line",
        files={"image": ("working.jpg", _a4_jpeg(), "image/jpeg")},
        data={
            "line_json": json.dumps({
                "text": "K555",
                "box": [[100, 100], [200, 100], [200, 130], [100, 130]],
            }),
            "reference": "A100",
            "replacement": "A200",
        },
    )

    assert response.status_code == 422
    assert response.json()["message"] == "La référence n'est pas présente dans la ligne OCR."
