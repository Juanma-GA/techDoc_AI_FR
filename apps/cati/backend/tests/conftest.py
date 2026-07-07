"""Pytest fixtures — force in-memory SQLite for isolation."""

from __future__ import annotations

import os
import tempfile

import pytest

# DB fichier temporaire (pas :memory:) : TestClient execute les routes dans un
# autre thread, or une base :memory: est par-connexion/thread -> les tables
# creees par la fixture y seraient invisibles. Un fichier est partage.
_TMP = tempfile.mkdtemp(prefix="cati_test_")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(_TMP, 'cati_test.db')}")
os.environ.setdefault("STORAGE_DIR", os.path.join(_TMP, "storage"))


@pytest.fixture(autouse=True)
def _tables():
    """Cree les tables (schema) sur l'engine de test avant chaque test."""
    import app.db.models  # noqa: F401 - enregistre les tables sur Base.metadata
    from app.db.session import Base, engine

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def app():
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


def _make_cati_pdf() -> bytes:
    """PDF synthetique minimal : une table CATI a 2 articles (3 sous-lignes chacun)."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    rows = [
        ["FIG REP", "DESIGNATION", "SYMBOLE", "IDENTIFICATION", "", "QUANTITE", "", "APP"],
        ["", "", "", "Code", "Reference", "ES", "EM", ""],
        ["10A", ".Piece A", "", "Client", "C1", "2", "", ""],
        ["", "", "", "Interne", "I1", "", "", ""],
        ["", "", "", "Fournisseur", "F1", "", "", ""],
        ["20A", ".Piece B", "", "Client", "C2", "5", "", ""],
        ["", "", "", "Interne", "I2", "", "", ""],
        ["", "", "", "Fournisseur", "F2", "", "", ""],
    ]
    x0, y0, rh = 30, 40, 26
    cw = [55, 110, 55, 60, 70, 35, 35, 40]
    xs = [x0]
    for w in cw:
        xs.append(xs[-1] + w)
    bottom = y0 + len(rows) * rh
    for ci in range(len(cw) + 1):
        page.draw_line((xs[ci], y0), (xs[ci], bottom))
    for ri, row in enumerate(rows):
        y = y0 + ri * rh
        page.draw_line((x0, y), (xs[-1], y))
        for ci, val in enumerate(row):
            if val:
                page.insert_text((xs[ci] + 2, y + 16), str(val), fontsize=8)
    page.draw_line((x0, bottom), (xs[-1], bottom))
    return doc.tobytes()


@pytest.fixture
def cati_pdf_bytes() -> bytes:
    return _make_cati_pdf()
