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
def pdf_bytes_headers() -> bytes:
    """PDF 3 pages avec un entete recurrent (haut) et un numero de page (bas),
    plus 2 titres de section pour que le decoupage produise des DMs."""
    import fitz

    doc = fitz.open()
    for i in range(1, 4):
        page = doc.new_page()
        h = page.rect.height
        page.insert_text((72, 24), "ACME MAINTENANCE MANUAL REF-4521", fontsize=9)
        page.insert_text((72, h - 24), f"Page {i}", fontsize=9)
        if i == 1:
            page.insert_text((72, 120), "1 Description", fontsize=18, fontname="hebo")
            page.insert_text((72, 150), "The pump supplies pressure.", fontsize=11)
        elif i == 2:
            page.insert_text((72, 120), "2 Removal Procedure", fontsize=18, fontname="hebo")
            page.insert_text((72, 150), "1. Disconnect the connector.", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_bytes_table() -> bytes:
    """PDF 1 page avec un tableau reglé (lignes + texte) pour `find_tables`."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 60), "1 Torque values", fontsize=18, fontname="hebo")
    # Grille 3x2 (entete + 2 lignes) tracee + texte dans les cellules.
    x0, y0, cw, rh, cols, rows = 72, 90, 120, 24, 3, 3
    for r in range(rows + 1):
        page.draw_line((x0, y0 + r * rh), (x0 + cols * cw, y0 + r * rh))
    for c in range(cols + 1):
        page.draw_line((x0 + c * cw, y0), (x0 + c * cw, y0 + rows * rh))
    cells = [["Bolt", "Torque", "Unit"], ["M6", "12", "Nm"], ["M8", "25", "Nm"]]
    for r, row in enumerate(cells):
        for c, val in enumerate(row):
            page.insert_text((x0 + c * cw + 6, y0 + r * rh + 16), val, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_bytes_image() -> bytes:
    """PDF 1 page avec une image embarquee + une legende 'Figure 1 ...'."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 60), "1 Description", fontsize=18, fontname="hebo")
    # Petite image RGB rouge 24x24 inseree dans la page.
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 80))
    pix.set_rect(pix.irect, (255, 0, 0))
    page.insert_image(fitz.Rect(72, 90, 168, 186), pixmap=pix)
    page.insert_text((72, 210), "Figure 1 Hydraulic pump location", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_bytes_repeated_image() -> bytes:
    """PDF 3 pages qui reutilisent LA MEME image (cas du logo / bandeau).

    Sert de garde-fou anti-duplication : une image reutilisee ne doit produire
    qu'un seul fichier extrait.
    """
    import fitz

    doc = fitz.open()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 24, 24))
    pix.set_rect(pix.irect, (0, 0, 255))
    for i in range(1, 4):
        page = doc.new_page()
        page.insert_text((72, 60), f"{i} Section {i}", fontsize=18, fontname="hebo")
        page.insert_image(fitz.Rect(72, 90, 168, 186), pixmap=pix)
        y = 220
        for j in range(6):
            page.insert_text(
                (72, y),
                f"Le circuit hydraulique alimente les actionneurs, paragraphe {j} de la page {i}.",
                fontsize=11,
            )
            y += 20
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
        '<dmodule><identAndStatusSection><dmAddress><dmIdent><dmCode '
        'modelIdentCode="TST" systemDiffCode="A" systemCode="A" subSystemCode="0" '
        'subSubSystemCode="0" assyCode="00" disassyCode="00" disassyCodeVariant="A" '
        'infoCode="040" infoCodeVariant="A" itemLocationCode="A"/>'
        "</dmIdent></dmAddress></identAndStatusSection>"
        "<content><brex><contextRules>"
        "<structureObjectRuleGroup>"
        "<structureObjectRule>"
        '<objectPath allowedObjectFlag="0">//emphasis</objectPath>'
        "<objectUse>Emphasis interdit par ce projet.</objectUse>"
        "</structureObjectRule>"
        "</structureObjectRuleGroup>"
        "</contextRules></brex></content></dmodule>"
    )
