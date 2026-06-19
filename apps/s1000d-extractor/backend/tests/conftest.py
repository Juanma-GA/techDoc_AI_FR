"""Fixtures pytest.

DB = fichier SQLite temporaire (pas `:memory:`) car l'extraction tourne dans un
thread separe : une base in-memory serait invisible d'un thread a l'autre.

Fixtures synthetiques uniquement (PDF/DOCX/BREX generes a la volee) - jamais de
donnee utilisateur reelle (regle CLAUDE.md).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.gettempdir())
_DB = _TMP / "s1000d_extractor_test.db"
_STORAGE = _TMP / "s1000d_extractor_test_storage"

os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["STORAGE_DIR"] = str(_STORAGE)
os.environ.setdefault("MISTRAL_API_KEY", "")  # pas de cle => pipeline heuristique


@pytest.fixture(scope="session", autouse=True)
def _schema():
    for f in (_DB, _DB.with_suffix(".db-wal"), _DB.with_suffix(".db-shm")):
        f.unlink(missing_ok=True)
    _STORAGE.mkdir(parents=True, exist_ok=True)
    import app.db.models  # noqa: F401  (enregistre les tables)
    from app.db.session import Base, engine

    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    """Purge les tables metier avant chaque test (isolation)."""
    from app.db.models import BrexProfile, Document
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        db.query(Document).delete()
        db.query(BrexProfile).delete()
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def app():
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def pdf_bytes() -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72

    def line(txt: str, size: float = 11.0, bold: bool = False) -> None:
        nonlocal y
        page.insert_text((72, y), txt, fontsize=size, fontname="hebo" if bold else "helv")
        y += size + 10

    line("1 Description", 18, True)
    line("The hydraulic system supplies pressure to the actuators.")
    line("2 Removal Procedure", 18, True)
    line("WARNING: Depressurize the system before any work.")
    line("1. Disconnect the electrical connector.")
    line("2. Loosen the four mounting bolts.")
    line("Figure 1 Hydraulic pump location")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def docx_bytes() -> bytes:
    import io

    from docx import Document

    d = Document()
    d.add_heading("Description", level=1)
    d.add_paragraph("The hydraulic system supplies pressure to the actuators.")
    d.add_paragraph("Pump", style="List Bullet")
    d.add_paragraph("Reservoir", style="List Bullet")
    d.add_heading("Removal Procedure", level=1)
    d.add_paragraph("Disconnect the electrical connector.", style="List Number")
    d.add_paragraph("Loosen the four mounting bolts.", style="List Number")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.fixture
def brex_xml() -> str:
    # BREX minimal : interdit l'element <emphasis> (allowedObjectFlag=0).
    return (
        '<?xml version="1.0"?>'
        "<dmodule><content><brex><contextRules>"
        "<structureObjectRuleGroup>"
        "<structureObjectRule>"
        '<objectPath allowedObjectFlag="0">//emphasis</objectPath>'
        "<objectUse>Emphasis interdit par ce projet.</objectUse>"
        "</structureObjectRule>"
        "</structureObjectRuleGroup>"
        "</contextRules></brex></content></dmodule>"
    )
