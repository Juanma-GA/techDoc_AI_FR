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
