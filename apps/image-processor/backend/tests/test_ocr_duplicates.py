from __future__ import annotations

import json
from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from openpyxl import Workbook
from PIL import Image, ImageDraw


def _image_bytes() -> bytes:
    image = BytesIO()
    canvas = Image.new("RGB", (180, 60), "white")
    ImageDraw.Draw(canvas).text((10, 12), "R-001 R-001 R-001", fill="black")
    canvas.save(image, format="PNG")
    return image.getvalue()


def _prediction(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        json={
            "res": {
                "rec_texts": [text],
                "rec_scores": [0.99],
                "rec_polys": [[[10, 10], [170, 10], [170, 30], [10, 30]]],
            }
        }
    )


def _workbook_bytes(
    reference: str = "R-001",
    replacements: tuple[str, str] = ("N-001", "N-002"),
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Repères"
    sheet.append(["Référence", "Colonne B", "Repère", "ICN", "Pièce"])
    sheet.append([None, None, None, "ICN-A", "Pompe A"])
    sheet.append([reference, None, replacements[0], None, None])
    sheet.append([reference, None, replacements[1], None, None])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_ocr_maps_duplicate_manual_references_to_occurrences_in_order(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.ocr.run_ocr_on_image",
        lambda image_bytes, timings=None: _prediction("R-001 R-001 R-001"),
    )

    response = client.post(
        "/api/v1/image-replace/ocr",
        files={"image": ("source.png", _image_bytes(), "image/png")},
        data={
            "replacement_pairs": (
                '[{"reference":"R-001","replacement":"101"},'
                '{"reference":"R-001","replacement":"202"}]'
            )
        },
    )

    assert response.status_code == 200, response.text
    assert [
        (item["reference"], item["replacement"], item["replacement_count"])
        for item in response.json()["references"]
    ] == [("R-001", "101", 1), ("R-001", "202", 1)]


def test_ocr_allows_duplicate_references_across_manual_and_excel_pairs(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.ocr.run_ocr_on_image",
        lambda image_bytes, timings=None: _prediction("R-001 R-001 R-001"),
    )

    response = client.post(
        "/api/v1/image-replace/ocr",
        files={
            "image": ("source.png", _image_bytes(), "image/png"),
            "workbook": (
                "mapping.xlsx",
                _workbook_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
        data={
            "replacement_pairs": '[{"reference":"R-001","replacement":"M-000"}]',
            "excel_sheet": "Repères",
            "excel_reference_column": "1",
            "excel_replacement_column": "3",
            "excel_icn_column": "4",
            "excel_piece_column": "5",
            "excel_piece_row": "2",
        },
    )

    assert response.status_code == 200, response.text
    assert [
        (item["replacement"], item["replacement_count"])
        for item in response.json()["references"]
    ] == [("M-000", 1), ("N-001", 1), ("N-002", 1)]


def test_ocr_applies_each_excel_marker_to_its_matching_occurrence(
    client: TestClient,
    monkeypatch,
) -> None:
    marker_pairs = [
        {"reference": "L104223", "replacement": "12"},
        {"reference": "L104223", "replacement": "13"},
    ]
    monkeypatch.setattr(
        "app.api.ocr.run_ocr_on_image",
        lambda image_bytes, timings=None: _prediction("L104223 L104223"),
    )

    response = client.post(
        "/api/v1/image-replace/ocr",
        files={
            "image": ("source.png", _image_bytes(), "image/png"),
            "workbook": (
                "mapping.xlsx",
                _workbook_bytes("L104223", ("12", "13")),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
        data={
            "replacement_pairs": "[]",
            "excel_sheet": "Repères",
            "excel_reference_column": "1",
            "excel_replacement_column": "3",
            "excel_icn_column": "4",
            "excel_piece_column": "5",
            "excel_piece_row": "2",
            "excel_replacement_pairs": json.dumps(marker_pairs),
        },
    )

    assert response.status_code == 200, response.text
    assert [
        (item["reference"], item["replacement"], item["replacement_count"])
        for item in response.json()["references"]
    ] == [("L104223", "12", 1), ("L104223", "13", 1)]


def test_ocr_does_not_reuse_one_occurrence_for_multiple_excel_markers(
    client: TestClient,
    monkeypatch,
) -> None:
    marker_pairs = [
        {"reference": "L104223", "replacement": "12"},
        {"reference": "L104223", "replacement": "13"},
    ]
    monkeypatch.setattr(
        "app.api.ocr.run_ocr_on_image",
        lambda image_bytes, timings=None: _prediction("L104223"),
    )

    response = client.post(
        "/api/v1/image-replace/ocr",
        files={
            "image": ("source.png", _image_bytes(), "image/png"),
            "workbook": (
                "mapping.xlsx",
                _workbook_bytes("L104223", ("12", "13")),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
        data={
            "replacement_pairs": "[]",
            "excel_sheet": "Repères",
            "excel_reference_column": "1",
            "excel_replacement_column": "3",
            "excel_icn_column": "4",
            "excel_piece_column": "5",
            "excel_piece_row": "2",
            "excel_replacement_pairs": json.dumps(marker_pairs),
        },
    )

    assert response.status_code == 200, response.text
    assert [
        (item["replacement"], item["found"], item["replacement_count"])
        for item in response.json()["references"]
    ] == [("12", True, 1), ("13", False, 0)]
