from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

from openpyxl import Workbook
from PIL import Image

from app.services.constants import A4_HEIGHT, A4_WIDTH
from app.services.image_layout import ICN_FOOTER_HEIGHT

BASE = "/api/v1/image-processor/ocr"


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Parts"
    sheet.append(["Reference", "Replacement", "ICN", "Part"])
    sheet.append(["", "00", "ICN-TEST.jpg", "Synthetic part"])
    sheet.append(["R-1", "N-1", "", ""])
    contents = BytesIO()
    workbook.save(contents)
    workbook.close()
    return contents.getvalue()


def test_ocr_renders_selected_icn_centered_in_black_footer(client, monkeypatch):
    source = BytesIO()
    Image.new("RGB", (120, 60), "white").save(source, format="PNG")
    monkeypatch.setattr(
        "app.api.ocr.run_ocr_on_image",
        lambda image_bytes, timings=None: SimpleNamespace(
            json={"res": {"rec_texts": [], "rec_scores": [], "rec_polys": []}},
        ),
    )
    response = client.post(
        BASE,
        files={
            "image": ("source.png", source.getvalue(), "image/png"),
            "workbook": ("mapping.xlsx", _workbook_bytes()),
        },
        data={
            "excel_sheet": "Parts",
            "excel_reference_column": "1",
            "excel_replacement_column": "2",
            "excel_icn_column": "3",
            "excel_piece_column": "4",
            "excel_piece_row": "2",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"] == "ICN-TEST.jpg"
    image_bytes = BytesIO(base64.b64decode(payload["edited_image"].split(",", 1)[1]))
    with Image.open(image_bytes) as result:
        assert result.size == (A4_WIDTH, A4_HEIGHT)
        footer = result.crop((0, A4_HEIGHT - ICN_FOOTER_HEIGHT, A4_WIDTH, A4_HEIGHT)).convert("L")
        dark_ink = footer.point([255 if value < 128 else 0 for value in range(256)])
        bounds = dark_ink.getbbox()
        assert bounds is not None
        assert abs((bounds[0] + bounds[2]) / 2 - A4_WIDTH / 2) <= 4
        assert bounds[3] - bounds[1] >= 32
