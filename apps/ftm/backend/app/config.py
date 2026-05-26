"""Application settings — loaded from env / .env via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # === App ===
    app_name: str = "ftm"
    app_version: str = "4.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # === Mistral ===
    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai"
    mistral_chat_model: str = "mistral-small-latest"
    mistral_embed_model: str = "mistral-embed"
    # Modèle multimodal pour la reconnaissance d'image (description). Pixtral
    # n'étant pas déployé sur tous les endpoints Mistral, on prend par défaut
    # un modèle medium multimodal largement disponible.
    mistral_vision_model: str = "mistral-medium-latest"
    # Modèle dédié à l'OCR (API /v1/ocr de Mistral).
    mistral_ocr_model: str = "mistral-ocr-latest"

    # === Storage / DB ===
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'ftm.db'}"
    storage_dir: str = str(BASE_DIR / "data" / "storage")

    # === HTTP / CORS / uploads ===
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
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

    @property
    def llm_configured(self) -> bool:
        return bool(self.mistral_api_key)


settings = Settings()
