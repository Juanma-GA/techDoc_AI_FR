"""Application settings — loaded from env / .env via pydantic-settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Image Replace"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    ocr_model_variant: Literal["medium", "small", "tiny"] = "medium"
    ocr_cpu_threads: int = Field(default=10, ge=1)

    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'image-replace.db'}"
    storage_dir: str = str(BASE_DIR / "data" / "storage")

    # Hote de bind uvicorn. Palier 1 (local) : 127.0.0.1. L'IT le passe a une
    # valeur exposee au deploiement (palier 2/3) via .env — ce qui rend les
    # protections sensibles OBLIGATOIRES (cf. main._validate_security_posture).
    bind_host: str = "127.0.0.1"

    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:8010",
        validation_alias="CORS_ORIGINS",
    )
    max_upload_size_mb: int = 50
    lama_service_port: int = 8011

    @property
    def cors_origins(self) -> list[str]:
        value = self.cors_origins_raw.strip()
        if not value:
            return []
        if value.startswith("["):
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError("CORS_ORIGINS must be a comma-separated or JSON list.")
            origins: list[str] = []
            for origin in parsed:
                if not isinstance(origin, str):
                    raise ValueError("CORS_ORIGINS must contain only strings.")
                origins.append(origin)
            return origins
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

settings = Settings()
