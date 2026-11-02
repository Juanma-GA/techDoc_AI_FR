"""Upgrade the normal and demo databases to the current schema."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config

from alembic import command
from app.config import settings
from app.db.session import demo_database_url

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _upgrade(database_url: str) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")


def upgrade_all_databases() -> None:
    _upgrade(settings.database_url)
    _upgrade(str(demo_database_url))


if __name__ == "__main__":
    upgrade_all_databases()
