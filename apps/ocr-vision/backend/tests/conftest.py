"""Pytest fixtures — force in-memory SQLite for isolation."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(autouse=True)
def _schema():
    """Cree le schema avant chaque test et le repart a zero apres (isolation).

    Les tests n'appliquent pas Alembic : on materialise directement
    `Base.metadata` sur l'engine (SQLite :memory: partage via StaticPool).
    """
    from app.db import models  # noqa: F401 — enregistre les tables sur Base.metadata
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
