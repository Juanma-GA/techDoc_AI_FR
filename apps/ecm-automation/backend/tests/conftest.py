"""Pytest fixtures — force in-memory SQLite for isolation."""

from __future__ import annotations

import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture
def app():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.main import create_app
    from app.db.session import Base, get_db

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    test_session = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def get_test_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    application = create_app()
    application.dependency_overrides[get_db] = get_test_db
    yield application
    test_engine.dispose()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)
