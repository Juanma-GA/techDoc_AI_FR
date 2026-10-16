"""Synthetic exports check the actual JPEG, selected ICN and error contract."""

from __future__ import annotations

import base64
from io import BytesIO
from urllib.parse import unquote

import pytest
from PIL import Image

from app.services.constants import A4_DPI, A4_HEIGHT, A4_WIDTH, MAX_IMAGE_BYTES

BASE = "/api/v1/image-replace/export"


def _image(workspace_state):
    return {
        "image": (
            "original-source.png",
            base64.b64decode(workspace_state["image"]["data_url"].split(",")[1]),
            "image/png",
        ),
    }


def _selection():
    return {
        "excel_sheet": "Parts", "excel_reference_column": "1", "excel_replacement_column": "2",
        "excel_icn_column": "3", "excel_piece_column": "4", "excel_piece_row": "2",
    }


@pytest.mark.parametrize("icn", ["ICN-TEST", "ICN-TEST.jpg", "ICN:TEST", "ICN-\u00e9"])
def test_export_uses_selected_icn_and_real_a4_jpeg(client, workspace_state, icn):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Parts"
    sheet.append(["Reference", "Replacement", "ICN", "Part"])
    sheet.append(["", "", icn, "Synthetic pump"])
    sheet.append(["R-1", "N-1", "", ""])
    contents = BytesIO()
    workbook.save(contents)
    workbook.close()
    files = {**_image(workspace_state), "workbook": ("synthetic.xlsx", contents.getvalue())}
    response = client.post(BASE, files=files, data={**_selection(), "filename": "wrong-retouched.jpg"})
    assert response.status_code == 200
    name = unquote(response.headers["Content-Disposition"].split("UTF-8''")[1])
    assert name == ({"ICN-TEST.jpg": "ICN-TEST", "ICN:TEST": "ICN_TEST"}.get(icn, icn)) + ".jpg"
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["X-Request-Id"]
    assert response.content.startswith(b"\xff\xd8\xff")
    with Image.open(BytesIO(response.content)) as image:
        assert image.format == "JPEG"
        assert image.size == (A4_WIDTH, A4_HEIGHT)
        assert image.info["dpi"] == (A4_DPI, A4_DPI)
        assert image.getpixel((A4_WIDTH // 2, A4_HEIGHT // 2)) == (255, 255, 255)


def test_export_without_excel_keeps_manual_and_previous_analysis_names(client, workspace_state):
    response = client.post(BASE, files=_image(workspace_state))
    assert response.status_code == 200
    assert response.headers["Content-Disposition"].endswith("original-source-modifiee.jpg")
    previous = client.post(BASE, files=_image(workspace_state), data={"filename": "ICN-PREVIOUS.jpg"})
    assert previous.status_code == 200
    assert previous.headers["Content-Disposition"].endswith("ICN-PREVIOUS.jpg")


def test_export_requires_valid_image_and_complete_excel_selection(client, workspace_state, excel_preset):
    assert client.post(BASE).status_code == 422
    assert client.post(BASE, files={"image": ("bad.png", b"not an image")}).status_code == 400
    assert client.post(BASE, files={"image": ("empty.png", b"")}).status_code == 400
    assert client.post(BASE, files=_image(workspace_state), data=_selection()).status_code == 422
    corrupted = bytearray(_image(workspace_state)["image"][1])
    corrupted[-13] ^= 255
    assert client.post(BASE, files={"image": ("bad-crc.png", bytes(corrupted))}).status_code == 400
    jpeg = BytesIO()
    Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white").save(
        jpeg, format="JPEG", dpi=(A4_DPI, A4_DPI),
    )
    assert client.post(BASE, files={"image": ("truncated.jpg", jpeg.getvalue()[:-20])}).status_code == 400
    workbook = base64.b64decode(excel_preset["workbook"]["data_url"].split(",")[1])
    files = {**_image(workspace_state), "workbook": ("synthetic.xlsx", workbook)}
    for data in (
        {}, {**_selection(), "excel_icn_column": "invalid"}, {**_selection(), "excel_piece_row": "3"},
    ):
        response = client.post(BASE, files=files, data=data)
        assert response.status_code == 422
        assert {"code", "message", "detail", "request_id"} <= response.json().keys()
        assert response.headers["X-Request-Id"]


def test_export_rejects_oversized_image(client):
    response = client.post(BASE, files={"image": ("large.png", b"x" * (MAX_IMAGE_BYTES + 1))})
    assert response.status_code == 413
