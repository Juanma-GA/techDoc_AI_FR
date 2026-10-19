"""Run Alembic only against a newly created database in pytest's temp directory."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def test_workspace_migration_preserves_config_and_round_trips(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'synthetic-migration.db'}"
    environment = {**os.environ, "DATABASE_URL": database_url}
    backend = Path(__file__).resolve().parents[1]

    def migrate(*arguments: str) -> None:
        subprocess.run(
            [sys.executable, "-m", "alembic", *arguments], cwd=backend, env=environment,
            capture_output=True, text=True, check=True,
        )

    migrate("upgrade", "0001_initial")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO app_config (key, value) VALUES ('synthetic', 'keep')"))
    migrate("upgrade", "head")
    expected = {"app_config", "excel_preset", "image_history", "file_asset"}
    assert expected <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT value FROM app_config WHERE key = 'synthetic'")) == "keep"
    migrate("check")
    migrate("downgrade", "0001_initial")
    assert "image_history" not in inspect(engine).get_table_names()
    migrate("upgrade", "head")
    assert "image_history" in inspect(engine).get_table_names()
    engine.dispose()
