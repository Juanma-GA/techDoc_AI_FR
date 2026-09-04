"""Pytest fixtures — force in-memory SQLite for isolation."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture
def app():
    import app.db.models  # noqa: F401 — registers models on Base.metadata
    from app.db.session import Base, engine
    from app.main import create_app

    Base.metadata.create_all(engine)
    return create_app()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)
