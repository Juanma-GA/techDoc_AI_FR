"""Pytest fixtures — SQLite fichier temporaire + tables auto-creees.

Fichier temporaire plutot que `:memory:` : le pool SQLAlchemy ouvre plusieurs
connexions et `:memory:` est isolee par connexion.
"""

from __future__ import annotations

import os
import tempfile

import pytest


_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"
os.environ.setdefault("STORAGE_DIR", tempfile.mkdtemp(prefix="catia-toolbox-storage-"))


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    from app.db import models  # noqa: F401  - enregistre les tables
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


@pytest.fixture
def synthetic_tree(tmp_path):
    """Cree une arborescence factice desordonnee (donnees 100% synthetiques).

    Aucune donnee utilisateur : noms inventes mimant un export CATIA messy
    (espaces, doublons de noms, nesting profond, extensions dispersees).
    """
    files = [
        "Assemblage Principal.CATProduct",
        "vieux/v1/sous/profond/encore/PIECE_001.CATPart",
        "vieux/v1/sous/profond/encore/PIECE_002.CATPart",
        "exports/PIECE_001.CATPart",  # doublon de basename
        "divers/Plan Ensemble.pdf",
        "divers/notes diverses.txt",
        "BREL/support.CATPart",
        "BREL/support.stp",
        "racine_piece.CATPart",
        "MAJUSCULE.STP",
    ]
    for rel in files:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("synthetic placeholder", encoding="utf-8")
    return tmp_path


@pytest.fixture(autouse=True)
def _isolate_db():
    """Nettoie les tables entre tests (ordre FK)."""
    from app.db import models
    from app.db.session import SessionLocal

    yield
    db = SessionLocal()
    try:
        for model in (
            models.DiffEntry,
            models.DiffRun,
            models.ConversionItem,
            models.ConversionRun,
            models.ColorizationItem,
            models.ColorizationRun,
            models.NomenclatureItem,
            models.NomenclatureRun,
            models.SmgxmlChange,
            models.SmgxmlRun,
            models.TreeNode,
            models.StructureImport,
            models.AppConfig,
        ):
            db.query(model).delete()
        db.commit()
    finally:
        db.close()
