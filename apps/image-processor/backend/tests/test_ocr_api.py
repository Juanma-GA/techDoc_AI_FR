from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from openpyxl import Workbook
from PIL import Image

from app.services.constants import A4_DPI, A4_HEIGHT, A4_WIDTH, OCR_DETECTION_MAX_SIDE


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Repères"
    sheet.append(["Référence", "Colonne B", "Repère", "ICN", "Pièce"])
    sheet.append([None, None, "00", "ICN-A", "Pompe A"])
    sheet.append(["R-001", "ligne de couple", "N-001", None, None])
    sheet.append([None, "référence manquante", "N-002", None, None])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_ocr_engine_selects_requested_v6_model_pair(monkeypatch) -> None:
    from app.services import ocr_inference

    captured: dict[str, object] = {}

    class FakePaddleModel:
        def __call__(self, *args: object, **kwargs: object) -> object:
            return iter(())

    class FakePaddleOCR:
        def __init__(self, **options: object) -> None:
            captured.update(options)
            self.paddlex_pipeline = SimpleNamespace(
                text_det_model=FakePaddleModel(),
                textline_orientation_model=FakePaddleModel(),
                text_rec_model=FakePaddleModel(),
            )

    model_pairs = {
        "medium": ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"),
        "small": ("PP-OCRv6_small_det", "PP-OCRv6_small_rec"),
        "tiny": ("PP-OCRv6_tiny_det", "PP-OCRv6_tiny_rec"),
    }
    monkeypatch.setattr("paddleocr.PaddleOCR", FakePaddleOCR)
    try:
        for variant, (detection_model, recognition_model) in model_pairs.items():
            captured.clear()
            ocr_inference.get_ocr_engine.cache_clear()
            monkeypatch.setattr(
                ocr_inference,
                "settings",
                SimpleNamespace(ocr_model_variant=variant, ocr_cpu_threads=6),
            )

            ocr_inference.get_ocr_engine()

            assert captured["text_detection_model_name"] == detection_model
            assert captured["text_recognition_model_name"] == recognition_model
            assert captured["device"] == "cpu"
            assert captured["cpu_threads"] == 6
            assert captured["enable_mkldnn"] is False
            assert captured["text_det_limit_side_len"] == OCR_DETECTION_MAX_SIDE
    finally:
        ocr_inference.get_ocr_engine.cache_clear()


def test_run_ocr_records_detection_and_recognition_timings(monkeypatch) -> None:
    from app.services import ocr_inference

    class FakePaddleModel:
        def __call__(self, *args: object, **kwargs: object) -> object:
            return iter((object(),))

    prediction = object()

    class FakePaddleOCR:
        def __init__(self, **options: object) -> None:
            self.paddlex_pipeline = SimpleNamespace(
                text_det_model=FakePaddleModel(),
                textline_orientation_model=FakePaddleModel(),
                text_rec_model=FakePaddleModel(),
            )

        def predict(self, input: str) -> list[object]:
            list(self.paddlex_pipeline.text_det_model(input))
            list(self.paddlex_pipeline.text_rec_model(input))
            return [prediction]

    monkeypatch.setattr("paddleocr.PaddleOCR", FakePaddleOCR)
    ocr_inference.get_ocr_engine.cache_clear()
    timings: dict[str, float] = {}
    try:
        assert ocr_inference.run_ocr_on_image(b"synthetic image", timings) is prediction
    finally:
        ocr_inference.get_ocr_engine.cache_clear()

    assert timings["ocr_detection_ms"] >= 0
    assert timings["ocr_recognition_ms"] >= 0


def test_ocr_route_combines_manual_and_excel_pairs(
    client: TestClient, monkeypatch, capsys, synthetic_ocr_image,
) -> None:
    image = BytesIO()
    synthetic_ocr_image.save(image, format="PNG")
    prediction = SimpleNamespace(
        json={
            "res": {
                "rec_texts": ["R-001 R-002"],
                "rec_scores": [0.99],
                "rec_polys": [[[10, 10], [110, 10], [110, 25], [10, 25]]],
            }
        }
    )

    def fake_ocr(image_bytes: bytes, timings: dict[str, float] | None = None) -> object:
        assert image_bytes
        if timings is not None:
            timings.update(
                ocr_temp_write_ms=0.1,
                ocr_engine_access_ms=0.2,
                ocr_detection_ms=0.1,
                ocr_recognition_ms=0.2,
                ocr_predict_ms=0.3,
            )
        return prediction

    monkeypatch.setattr("app.api.ocr.run_ocr_on_image", fake_ocr)

    response = client.post(
        "/api/v1/image-processor/ocr",
        files={
            "image": ("source.png", image.getvalue(), "image/png"),
            "workbook": (
                "mapping.xlsx",
                _workbook_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
        data={
            "replacement_pairs": '[{"reference":"R-002","replacement":"M-002"}]',
            "excel_sheet": "Repères",
            "excel_reference_column": "1",
            "excel_replacement_column": "3",
            "excel_icn_column": "4",
            "excel_piece_column": "5",
            "excel_piece_row": "2",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"] == "ICN-A.jpg"
    assert (payload["width"], payload["height"]) == (A4_WIDTH, A4_HEIGHT)
    assert [item["replacement"] for item in payload["references"]] == ["M-002", "N-001"]
    assert all(item["replacement_count"] == 1 for item in payload["references"])
    assert payload["edited_image"].startswith("data:image/jpeg;base64,")
    logged_output = capsys.readouterr().out
    assert "image_ocr_timing" in logged_output
    assert "ocr_engine_access_ms" in logged_output
    assert "ocr_detection_ms" in logged_output
    assert "ocr_recognition_ms" in logged_output
    assert "ocr_model_variant" in logged_output
    assert "ocr_cpu_threads" in logged_output

    jpeg_bytes = base64.b64decode(payload["edited_image"].split(",", 1)[1])
    with Image.open(BytesIO(jpeg_bytes)) as output_image:
        assert output_image.format == "JPEG"
        assert output_image.size == (A4_WIDTH, A4_HEIGHT)
        assert output_image.info["dpi"] == (A4_DPI, A4_DPI)


def test_ocr_comparison_only_does_not_replace_text(
    client: TestClient, monkeypatch, synthetic_ocr_image,
) -> None:
    image = BytesIO()
    synthetic_ocr_image.save(image, format="PNG")
    prediction = SimpleNamespace(
        json={
            "res": {
                "rec_texts": ["XXXYY*"],
                "rec_scores": [0.99],
                "rec_polys": [[[10, 10], [110, 10], [110, 25], [10, 25]]],
            }
        }
    )
    monkeypatch.setattr(
        "app.api.ocr.run_ocr_on_image",
        lambda image_bytes, timings=None: prediction,
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Comparison-only OCR must not apply replacements.")

    monkeypatch.setattr("app.api.ocr.apply_replacements", fail_if_called)
    response = client.post(
        "/api/v1/image-processor/ocr",
        files={"image": ("source.png", image.getvalue(), "image/png")},
        data={
            "replacement_pairs": (
                '[{"reference":"XXXY","replacement":"XXXZ"},'
                '{"reference":"MISSING","replacement":""}]'
            ),
            "comparison_only": "true",
        },
    )

    assert response.status_code == 200, response.text
    references = response.json()["references"]
    assert [(item["reference"], item["found"]) for item in references] == [
        ("XXXY", False),
        ("MISSING", False),
    ]
    assert references[0]["replacement"] == "XXXZ"
    assert "replacement_count" not in references[0]


def test_ocr_comparison_only_accepts_excel_references_without_replacements(
    client: TestClient, monkeypatch, synthetic_ocr_image,
) -> None:
    image = BytesIO()
    synthetic_ocr_image.save(image, format="PNG")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Repères"
    sheet.append(["Référence", "Colonne B", "Repère", "ICN", "Pièce"])
    sheet.append([None, None, "00", "ICN-A", "Pompe A"])
    sheet.append(["R-001", None, None, None, None])
    workbook_output = BytesIO()
    workbook.save(workbook_output)
    prediction = SimpleNamespace(
        json={
            "res": {
                "rec_texts": ["R-001"],
                "rec_scores": [0.99],
                "rec_polys": [[[10, 10], [110, 10], [110, 25], [10, 25]]],
            }
        }
    )
    monkeypatch.setattr(
        "app.api.ocr.run_ocr_on_image",
        lambda image_bytes, timings=None: prediction,
    )

    response = client.post(
        "/api/v1/image-processor/ocr",
        files={
            "image": ("source.png", image.getvalue(), "image/png"),
            "workbook": (
                "mapping.xlsx",
                workbook_output.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
        data={
            "excel_sheet": "Repères",
            "excel_reference_column": "1",
            "excel_replacement_column": "3",
            "excel_icn_column": "4",
            "excel_piece_column": "5",
            "excel_piece_row": "2",
            "excel_replacement_pairs": '[{"reference":"R-001","replacement":""}]',
            "comparison_only": "true",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["references"][0]["reference"] == "R-001"
    assert response.json()["references"][0]["found"] is True
    assert response.json()["references"][0]["replacement"] == ""


def test_ocr_route_uses_edited_and_removed_excel_pairs(
    client: TestClient, monkeypatch, synthetic_ocr_image,
) -> None:
    image = BytesIO()
    synthetic_ocr_image.save(image, format="PNG")
    prediction = SimpleNamespace(
        json={
            "res": {
                "rec_texts": ["R-001"],
                "rec_scores": [0.99],
                "rec_polys": [[[10, 10], [110, 10], [110, 25], [10, 25]]],
            }
        }
    )
    monkeypatch.setattr(
        "app.api.ocr.run_ocr_on_image",
        lambda image_bytes, timings=None: prediction,
    )
    files = {
        "image": ("source.png", image.getvalue(), "image/png"),
        "workbook": (
            "mapping.xlsx",
            _workbook_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }
    excel_selection = {
        "excel_sheet": "Repères",
        "excel_reference_column": "1",
        "excel_replacement_column": "3",
        "excel_icn_column": "4",
        "excel_piece_column": "5",
        "excel_piece_row": "2",
    }

    edited_response = client.post(
        "/api/v1/image-processor/ocr",
        files=files,
        data={
            **excel_selection,
            "excel_replacement_pairs": '[{"reference":"R-001","replacement":"N-999"}]',
        },
    )
    removed_response = client.post(
        "/api/v1/image-processor/ocr",
        files=files,
        data={**excel_selection, "excel_replacement_pairs": "[]"},
    )
    extracted_response = client.post(
        "/api/v1/image-processor/ocr",
        files=files,
        data=excel_selection,
    )
    empty_reference_response = client.post(
        "/api/v1/image-processor/ocr",
        files=files,
        data={
            **excel_selection,
            "excel_replacement_pairs": '[{"reference":"","replacement":"N-999"}]',
        },
    )

    assert edited_response.status_code == 200, edited_response.text
    assert [item["replacement"] for item in edited_response.json()["references"]] == ["N-999"]
    assert removed_response.status_code == 200, removed_response.text
    assert removed_response.json()["references"] == []
    assert extracted_response.status_code == 200, extracted_response.text
    assert [item["replacement"] for item in extracted_response.json()["references"]] == ["N-001"]
    assert empty_reference_response.status_code == 200, empty_reference_response.text
    assert empty_reference_response.json()["references"] == []


def test_ocr_route_rejects_non_image_upload(client: TestClient) -> None:
    response = client.post(
        "/api/v1/image-processor/ocr",
        files={"image": ("notes.txt", b"synthetic text", "text/plain")},
    )

    assert response.status_code == 400
