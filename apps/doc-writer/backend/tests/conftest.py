"""Pytest fixtures — SQLite isolée + tables auto-créées via Base.metadata.

On utilise un fichier temporaire plutôt que `:memory:` car le pool SQLAlchemy
ouvre plusieurs connexions et `:memory:` est isolée par connexion.
"""

from __future__ import annotations

import os
import tempfile

import pytest


_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"
os.environ.setdefault("STORAGE_DIR", tempfile.mkdtemp(prefix="doc-writer-storage-"))


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    from app.db import models  # noqa: F401  — register tables
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


@pytest.fixture(autouse=True)
def _isolate_db():
    """Nettoie les tables entre tests pour éviter les fuites d'état."""
    from app.db import models
    from app.db.session import SessionLocal

    yield
    db = SessionLocal()
    try:
        db.query(models.Message).delete()
        db.query(models.Session).delete()
        db.query(models.DocumentChunk).delete()
        db.query(models.Document).delete()
        db.query(models.AppConfig).delete()
        db.commit()
    finally:
        db.close()
