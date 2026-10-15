from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from openpyxl import Workbook
from PIL import Image

from app.services.constants import A4_DPI, A4_HEIGHT, A4_WIDTH


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Repères"
    sheet.append(["Référence", "Colonne B", "Repère", "ICN", "Pièce"])
    sheet.append([None, None, None, "ICN-A", "Pompe A"])
    sheet.append(["R-001", "ligne de couple", "N-001", None, None])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_ocr_route_combines_manual_and_excel_pairs(client: TestClient, monkeypatch) -> None:
    image = BytesIO()
    Image.new("RGB", (120, 60), "white").save(image, format="PNG")
    prediction = SimpleNamespace(
        json={
            "res": {
                "rec_texts": ["R-001 R-002"],
                "rec_scores": [0.99],
                "rec_polys": [[[10, 10], [110, 10], [110, 25], [10, 25]]],
            }
        }
    )
    monkeypatch.setattr("app.api.ocr.run_ocr_on_image", lambda image_bytes: prediction)

    response = client.post(
        "/api/v1/image-replace/ocr",
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

    jpeg_bytes = base64.b64decode(payload["edited_image"].split(",", 1)[1])
    with Image.open(BytesIO(jpeg_bytes)) as output_image:
        assert output_image.format == "JPEG"
        assert output_image.size == (A4_WIDTH, A4_HEIGHT)
        assert output_image.info["dpi"] == (A4_DPI, A4_DPI)


def test_ocr_route_rejects_non_image_upload(client: TestClient) -> None:
    response = client.post(
        "/api/v1/image-replace/ocr",
        files={"image": ("notes.txt", b"synthetic text", "text/plain")},
    )

    assert response.status_code == 400
