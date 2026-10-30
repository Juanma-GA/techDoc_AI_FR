from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_migration_purges_provider_config_and_preserves_demo_mode(tmp_path, monkeypatch) -> None:
    from app.config import settings
    from app.core.demo_mode import DEMO_MODE_KEY

    database_path = tmp_path / "config-cleanup.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{database_path}")
    config = Config()
    config.set_main_option("script_location", "alembic")
    command.upgrade(config, "0011_preliminary_review")

    engine = create_engine(f"sqlite:///{database_path}")
    provider_keys = (
        "MISTRAL_API_KEY",
        "MISTRAL_BASE_URL",
        "MISTRAL_CHAT_MODEL",
        "MISTRAL_EMBED_MODEL",
        "MISTRAL_OCR_MODEL",
        "llm_enabled",
        "llm_last_test_ok",
    )
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app_config (key, value) VALUES (:key, :value)"),
            [{"key": key, "value": "synthetic"} for key in provider_keys],
        )
        connection.execute(
            text("INSERT INTO app_config (key, value) VALUES (:key, :value)"),
            {"key": DEMO_MODE_KEY, "value": "true"},
        )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        remaining = dict(connection.execute(text("SELECT key, value FROM app_config")).all())
    engine.dispose()

    assert remaining == {DEMO_MODE_KEY: "true"}
