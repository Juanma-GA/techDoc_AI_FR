"""Pytest fixtures — force in-memory SQLite for isolation."""

from __future__ import annotations

import os

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
