from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.ocr_engine import _build_lines
from app.services.text_geometry import reading_order_box, text_frame


@pytest.mark.parametrize(
    ("overrides", "source", "skip_check"),
    [
        ({}, "bos", "True"),
        (
            {"PADDLE_PDX_MODEL_SOURCE": "huggingface", "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "1"},
            "huggingface",
            "1",
        ),
    ],
)
def test_download_defaults_apply_before_paddle_import_and_preserve_overrides(
    overrides, source, skip_check,
):
    environment = os.environ.copy()
    for name in ("PADDLE_PDX_MODEL_SOURCE", "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"):
        environment.pop(name, None)
    environment.update(overrides)
    script = (
        "from app.services import ocr_inference\n"
        "import os\n"
        f"assert os.environ['PADDLE_PDX_MODEL_SOURCE'] == {source!r}\n"
        f"assert os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] == {skip_check!r}\n"
        "from paddlex.utils.flags import MODEL_SOURCE, DISABLE_MODEL_SOURCE_CHECK\n"
        f"assert MODEL_SOURCE == {source!r}\n"
        "assert bool(DISABLE_MODEL_SOURCE_CHECK)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
        env=environment, capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(("indicator", "expected"), [(0, 90), (1, -90), (180, -90)])
def test_vertical_reading_direction_includes_crop_rotation_and_classifier(indicator, expected):
    box = [[10, 10], [30, 10], [30, 110], [10, 110]]
    assert text_frame(reading_order_box(box, indicator)).angle == pytest.approx(expected)


@pytest.mark.parametrize("indicator", [1, 180])
def test_upside_down_horizontal_text_keeps_its_reading_direction(indicator):
    box = [[10, 10], [110, 10], [110, 30], [10, 30]]
    assert abs(text_frame(reading_order_box(box, indicator)).angle) == 180


def test_narrow_single_digit_is_not_mistaken_for_a_vertical_line():
    prediction = SimpleNamespace(json={"res": {
        "rec_texts": ["1"], "rec_scores": [0.99], "rec_boxes": [[10, 10, 18, 30]],
        "textline_orientation_angles": [0],
    }})
    assert text_frame(_build_lines(prediction)[0]["box"]).angle == 0


def test_empty_recognized_lines_are_skipped():
    first = [[10, 10], [110, 10], [110, 30], [10, 30]]
    second = [[10, 60], [110, 60], [110, 80], [10, 80]]
    third = [[10, 110], [110, 110], [110, 130], [10, 130]]
    prediction = SimpleNamespace(json={"res": {
        "rec_texts": ["", "R-001", "   "],
        "rec_scores": [0.99, 0.99, 0.99],
        "rec_polys": [first, second, third],
    }})

    lines = _build_lines(prediction)

    assert len(lines) == 1
    assert lines[0]["text"] == "R-001"


def test_tall_crop_test_uses_maximum_edge_lengths_not_average_lengths():
    box = [[0, 0], [120, 0], [100, 150], [20, 150]]
    assert reading_order_box(box, 0) == box


def test_classifier_angles_stay_aligned_after_recognition_filters_a_detection():
    first = [[10, 10], [110, 10], [110, 30], [10, 30]]
    second = [[10, 60], [110, 60], [110, 80], [10, 80]]
    prediction = SimpleNamespace(json={"res": {
        "rec_texts": ["R2"], "rec_scores": [0.99], "rec_polys": [second],
        "dt_polys": [first, second], "textline_orientation_angles": [0, 1],
    }})
    lines = _build_lines(prediction)
    assert lines[0]["box"] == second[2:] + second[:2]


def test_incompatible_orientation_metadata_is_rejected():
    prediction = SimpleNamespace(json={"res": {
        "rec_texts": ["R1"], "rec_scores": [0.99], "rec_boxes": [[10, 10, 100, 30]],
        "textline_orientation_angles": [0, 1],
    }})
    with pytest.raises(RuntimeError, match="orientations incompatibles"):
        _build_lines(prediction)


def test_standard_orientation_model_is_enabled_and_timed_without_model_download(monkeypatch):
    from app.services import ocr_inference

    options = {}

    class Model:
        def __call__(self, *args, **kwargs):
            return iter([object()])

    prediction = object()

    class Engine:
        def __init__(self, **kwargs):
            options.update(kwargs)
            self.paddlex_pipeline = SimpleNamespace(
                text_det_model=Model(), textline_orientation_model=Model(), text_rec_model=Model(),
            )

        def predict(self, input):
            list(self.paddlex_pipeline.text_det_model(input))
            list(self.paddlex_pipeline.textline_orientation_model(input))
            list(self.paddlex_pipeline.text_rec_model(input))
            return [prediction]

    monkeypatch.setattr("paddleocr.PaddleOCR", Engine)
    ocr_inference.get_ocr_engine.cache_clear()
    timings = {}
    try:
        assert ocr_inference.run_ocr_on_image(b"synthetic", timings) is prediction
    finally:
        ocr_inference.get_ocr_engine.cache_clear()
    assert options["use_textline_orientation"] is True
    assert options["textline_orientation_model_name"] == "PP-LCNet_x1_0_textline_ori"
    assert options["textline_orientation_batch_size"] == 1
    assert timings["ocr_orientation_ms"] >= 0
