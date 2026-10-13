"""Application settings — loaded from env / .env via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


def _default_database_url() -> str:
    legacy_database = BASE_DIR / "data" / "ecm-rename.db"
    if legacy_database.is_file():
        return f"sqlite:///{legacy_database}"
    return f"sqlite:///{BASE_DIR / 'data' / 'ecm-automation.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ECM Automation"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = Field(default_factory=_default_database_url)
    storage_dir: str = str(BASE_DIR / "data" / "storage")

    # Hote de bind uvicorn. En local : 127.0.0.1. Un bind expose doit utiliser
    # une liste CORS configuree pour les origines autorisees.
    bind_host: str = "127.0.0.1"

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8009",
    ]
    max_upload_size_mb: int = 50

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
