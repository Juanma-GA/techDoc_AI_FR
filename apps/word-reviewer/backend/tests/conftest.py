"""Pytest fixtures - DB SQLite temporaire (fichier) + seed ATA100 + helpers docx.

On utilise un fichier temporaire (pas `:memory:`) car le TestClient ouvre
plusieurs connexions ; les tables doivent etre partagees. Aucune donnee client
reelle : tout est synthetique.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.gettempdir()) / "word_reviewer_test"
_TMP.mkdir(exist_ok=True)
_DB = _TMP / "test.db"
if _DB.exists():
    _DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["MISTRAL_API_KEY"] = ""  # passe LLM desactivee dans les tests


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    from app.db import models  # noqa: F401 — enregistre les tables
    from app.db.seed import seed_builtin_standards
    from app.db.session import Base, SessionLocal, engine

    Base.metadata.create_all(engine)
    db = SessionLocal()
    seed_builtin_standards(db)
    db.close()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import create_app

    return TestClient(create_app())


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _docx_bytes(paragraphs, footer=None, headings=None):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    align_map = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }
    d = Document()
    for h in headings or []:
        d.add_heading(h, level=1)
    for item in paragraphs:
        if isinstance(item, tuple):
            text, align = item
            p = d.add_paragraph(text)
            if align in align_map:
                p.alignment = align_map[align]
        else:
            d.add_paragraph(item)
    if footer is not None:
        d.sections[0].footer.paragraphs[0].text = footer
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.fixture
def make_docx():
    return _docx_bytes


@pytest.fixture
def make_checklist():
    def _build(rows: list[tuple[str, str]]) -> bytes:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["Topic", "Check"])
        for topic, check in rows:
            ws.append([topic, check])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    return _build
