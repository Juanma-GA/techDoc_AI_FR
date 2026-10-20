from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import ocr_local
from app.core import ocr_mistral
from app.core.ocr_output import extract_result


def test_extract_paddle_text_boxes_and_confidence_from_result_shape() -> None:
    payload = {
        "res": {
            "rec_texts": ["Torque limit", "  "],
            "rec_scores": [0.95, 0.4],
            "rec_boxes": [[100, 200, 500, 260], [600, 300, 900, 360]],
        }
    }

    text, boxes = extract_result(
        payload,
        image_width=2000,
        image_height=4000,
        coordinate_mode="pixels",
    )

    assert text == "Torque limit"
    assert len(boxes) == 1
    assert boxes[0].x0 == pytest.approx(0.05)
    assert boxes[0].y0 == pytest.approx(0.05)
    assert boxes[0].x1 == pytest.approx(0.25)
    assert boxes[0].confidence == pytest.approx(0.95)


def test_extract_indra_lines_without_duplicating_markdown() -> None:
    payload = {
        "markdown": "Section title\nNext line",
        "lines": [
            {"text": "Section title", "box": [100, 200, 500, 250], "conf": 0.91},
            {"text": "Next line", "box": [100, 300, 400, 350], "conf": 0.88},
        ],
        "blocks": [{"text": "Section title\nNext line", "bbox": [90, 190, 510, 360]}],
    }

    text, boxes = extract_result(
        payload,
        image_width=2000,
        image_height=4000,
        coordinate_mode="pixels",
    )

    assert text == "Section title\nNext line"
    assert len(boxes) == 2
    assert boxes[0].confidence == pytest.approx(0.91)
    assert boxes[0].x0 == pytest.approx(0.05)


def test_extract_mistral_blocks_without_repeating_page_markdown() -> None:
    payload = {
        "pages": [
            {
                "markdown": "Section title\nNext line",
                "blocks": [
                    {"text": "Section title", "bbox": [50, 100, 250, 140]},
                    {"text": "Next line", "bbox": [50, 150, 220, 190]},
                ],
            }
        ]
    }

    text, boxes = extract_result(payload, image_width=1000, image_height=2000)

    assert text == "Section title\nNext line"
    assert len(boxes) == 2


def test_paddle_adapter_uses_supported_tiny_models_and_json_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    executable = tmp_path / "python.exe"
    executable.touch()

    def fake_run(command: list[str], _provider: str, *, env=None) -> str:
        captured["command"] = command
        output_path = Path(command[command.index("--output") + 1])
        output_path.write_text(
            json.dumps(
                {
                    "res": {
                        "rec_texts": ["ATA 32"],
                        "rec_scores": [0.9],
                        "rec_boxes": [[10, 20, 50, 30]],
                    }
                }
            ),
            encoding="utf-8",
        )
        return ""

    monkeypatch.setattr(ocr_local.settings, "paddleocr_python", str(executable))
    monkeypatch.setattr(ocr_local.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ocr_local, "_run_command", fake_run)

    text, boxes = ocr_local.run_paddle_ocr(b"image", image_width=100, image_height=200)

    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == str(executable)
    assert command[1].endswith("app\\paddleocr_worker.py")
    assert text == "ATA 32"
    assert len(boxes) == 1


def test_paddle_provider_uses_backend_python_when_optional_packages_are_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ocr_local.settings, "paddleocr_python", "")
    monkeypatch.setattr(
        ocr_local.importlib.util,
        "find_spec",
        lambda module: object() if module in {"paddle", "paddleocr"} else None,
    )

    assert ocr_local.local_provider_available("paddle")
    assert ocr_local._paddleocr_python() == ocr_local.sys.executable


def test_mistral_ocr_uses_the_persisted_model_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Response:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {"pages": [{"markdown": "ATA 32"}]}

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, _url: str, *, headers: dict[str, str], json: dict[str, object]) -> Response:
            captured["model"] = json["model"]
            return Response()

    monkeypatch.setattr(ocr_mistral, "get_llm_enabled", lambda _db: True)
    monkeypatch.setattr(
        ocr_mistral,
        "get_endpoint",
        lambda _db: {
            "api_key": "synthetic-key",
            "base_url": "https://api.mistral.ai",
            "ocr_model": "mistral-ocr-custom",
        },
    )
    monkeypatch.setattr(ocr_mistral.httpx, "Client", Client)

    text, boxes = ocr_mistral.run_mistral_ocr(b"synthetic", 100, 100, object())

    assert captured["model"] == "mistral-ocr-custom"
    assert text == "ATA 32"
    assert boxes == []
