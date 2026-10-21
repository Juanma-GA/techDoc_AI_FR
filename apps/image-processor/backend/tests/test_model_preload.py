from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.main import create_app
from lama_service.app import app as lama_app


def test_desktop_model_preload_defaults_to_disabled(monkeypatch) -> None:
    monkeypatch.delenv("DESKTOP_PRELOAD_MODELS", raising=False)

    assert Settings(_env_file=None).desktop_preload_models is False


def test_desktop_model_preload_can_be_enabled_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("DESKTOP_PRELOAD_MODELS", "true")

    assert Settings(_env_file=None).desktop_preload_models is True


def test_api_preloads_ocr_model_when_enabled(monkeypatch) -> None:
    warmed: list[str] = []
    monkeypatch.setattr(settings, "desktop_preload_models", True)
    monkeypatch.setattr("app.main.get_ocr_engine", lambda: warmed.append("ocr"))

    with TestClient(create_app()):
        pass

    assert warmed == ["ocr"]


def test_api_keeps_ocr_model_lazy_when_disabled(monkeypatch) -> None:
    warmed: list[str] = []
    monkeypatch.setattr(settings, "desktop_preload_models", False)
    monkeypatch.setattr("app.main.get_ocr_engine", lambda: warmed.append("ocr"))

    with TestClient(create_app()):
        pass

    assert warmed == []


def test_lama_preloads_model_when_enabled(monkeypatch) -> None:
    warmed: list[str] = []
    monkeypatch.setenv("DESKTOP_PRELOAD_MODELS", "true")
    monkeypatch.setattr("lama_service.app.get_lama", lambda: warmed.append("lama"))

    with TestClient(lama_app):
        pass

    assert warmed == ["lama"]


def test_lama_keeps_model_lazy_when_disabled(monkeypatch) -> None:
    warmed: list[str] = []
    monkeypatch.delenv("DESKTOP_PRELOAD_MODELS", raising=False)
    monkeypatch.setattr("lama_service.app.get_lama", lambda: warmed.append("lama"))

    with TestClient(lama_app):
        pass

    assert warmed == []
