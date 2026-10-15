"""Settings API tests for the persisted demo-mode preference."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import create_app


@pytest.fixture
def demo_client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_demo_mode_defaults_to_normal(demo_client: TestClient) -> None:
    response = demo_client.get("/api/v1/settings")

    assert response.status_code == 200
    assert response.json()["demo_enabled"] is False


def test_demo_mode_setting_persists(demo_client: TestClient) -> None:
    response = demo_client.post("/api/v1/settings", json={"demo_enabled": True})

    assert response.status_code == 200
    assert response.json()["demo_enabled"] is True

    persisted = demo_client.get("/api/v1/settings")
    assert persisted.status_code == 200
    assert persisted.json()["demo_enabled"] is True