"""Pytest fixtures — force in-memory SQLite for isolation."""

from __future__ import annotations

import base64
import os
from collections.abc import Iterator
from io import BytesIO

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture
def app():
    from app.main import create_app

    return create_app()


@pytest.fixture
def synthetic_ocr_image():
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (120, 60), "white")
    ImageDraw.Draw(image).text(
        (10, 10), "R-001 R-002", fill="black", font=ImageFont.load_default(size=14), anchor="lt",
    )
    return image


@pytest.fixture
def typography_sample():
    from math import cos, radians, sin

    from PIL import Image, ImageDraw

    from app.services.replacement_typography import load_replacement_font

    def create(text="R123", size=24, angle=0, padding=12, background=(255, 255, 255)):
        font = load_replacement_font(size)
        box = font.getbbox(text)
        width, height = box[2] - box[0], box[3] - box[1]
        layer = Image.new("RGBA", (width + padding * 2, height + padding * 2))
        ImageDraw.Draw(layer).text(
            (padding - box[0], padding - box[1]), text, font=font, fill=(0, 0, 0, 255),
        )
        rotated = layer.rotate(-angle, expand=True, resample=Image.Resampling.BICUBIC)
        image = Image.new("RGB", (400, 300), background)
        image.paste(rotated, (round(200 - rotated.width / 2), round(150 - rotated.height / 2)), rotated)
        cosine, sine = cos(radians(angle)), sin(radians(angle))
        polygon = [
            [200 + x * cosine - y * sine, 150 + x * sine + y * cosine]
            for x, y in (
                (-layer.width / 2, -layer.height / 2), (layer.width / 2, -layer.height / 2),
                (layer.width / 2, layer.height / 2), (-layer.width / 2, layer.height / 2),
            )
        ]
        return image, polygon, height

    return create


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def workspace_client(tmp_path, monkeypatch) -> Iterator:
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.config import settings
    from app.db.session import Base, get_db
    from app.main import create_app

    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "storage"))

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override_db() -> Iterator[Session]:
        with factory() as db:
            yield db

    application = create_app()
    application.dependency_overrides[get_db] = override_db
    with TestClient(application) as test_client:
        yield test_client
    engine.dispose()


@pytest.fixture
def excel_preset() -> dict:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Parts"
    sheet.append(["Reference", "Replacement", "ICN", "Part"])
    sheet.append(["", "", "ICN-TEST", "Synthetic pump"])
    sheet.append(["R-1", "N-1", "", ""])
    contents = BytesIO()
    workbook.save(contents)
    workbook.close()
    return {
        "workbook": {
            "name": "synthetic.xlsx",
            "data_url": "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,"
            + base64.b64encode(contents.getvalue()).decode("ascii"),
        },
        "sheets": ["Parts"], "sheet": "Parts",
        "columns": [
            {"index": index, "letter": letter, "header": header, "label": header}
            for index, letter, header in [
                (1, "A", "Reference"), (2, "B", "Replacement"), (3, "C", "ICN"), (4, "D", "Part"),
            ]
        ],
        "referenceColumn": "1", "replacementColumn": "2", "icnColumn": "3", "pieceColumn": "4",
        "pieces": [{"row": 2, "name": "Synthetic pump"}],
    }


@pytest.fixture
def workspace_state(excel_preset) -> dict:
    from PIL import Image

    contents = BytesIO()
    Image.new("RGB", (20, 30), "white").save(contents, format="PNG")
    image = {
        "name": "synthetic.png",
        "data_url": "data:image/png;base64," + base64.b64encode(contents.getvalue()).decode("ascii"),
    }
    pair = {"id": 7, "reference": "R-1", "replacement": "N-9", "enabled": False}
    return {
        "schema_version": 1, "image": image,
        "excel": {**excel_preset, "pieceRow": "2", "pairs": [pair]},
        "manualPairs": [{"id": 3, "reference": "R-2", "replacement": "N-2", "enabled": True}],
        "revisions": [{"image": image, "kind": "brush-color", "analysis": None}],
        "operations": [{"kind": "brush-color", "at": "2026-10-16T10:00:00Z"}],
    }
