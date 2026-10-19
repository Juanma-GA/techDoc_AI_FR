"""Settings API tests for the persisted demo-mode preference."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.session import Base, get_db
from app.main import create_app


@pytest.mark.parametrize(
    ("cors_origins", "expected"),
    [
        (
            "http://localhost:5173,http://127.0.0.1:5173",
            ["http://localhost:5173", "http://127.0.0.1:5173"],
        ),
        (
            '["http://localhost:5173", "http://127.0.0.1:5173"]',
            ["http://localhost:5173", "http://127.0.0.1:5173"],
        ),
        ("", []),
    ],
)
def test_cors_origins_accept_csv_and_json_dotenv(tmp_path, cors_origins, expected) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(f"CORS_ORIGINS={cors_origins}\n", encoding="utf-8")

    settings = Settings(_env_file=dotenv_path)

    assert settings.cors_origins == expected


@pytest.mark.parametrize("cpu_threads", [8, 16])
def test_ocr_cpu_threads_can_be_set_in_dotenv(tmp_path, cpu_threads) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(f"OCR_CPU_THREADS={cpu_threads}\n", encoding="utf-8")

    settings = Settings(_env_file=dotenv_path)

    assert settings.ocr_cpu_threads == cpu_threads


def test_ocr_model_variant_defaults_to_tiny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OCR_MODEL_VARIANT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.ocr_model_variant == "tiny"


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
