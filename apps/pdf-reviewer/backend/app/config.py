"""Application settings — loaded from env / .env via pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

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

    app_name: str = "pdf-reviewer"
    app_version: str = "2.0.0"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'pdf-reviewer.db'}"
    storage_dir: str = str(BASE_DIR / "data" / "storage")

    # Hote de bind uvicorn. Palier 1 (local) : 127.0.0.1. L'IT le passe a une
    # valeur exposee au deploiement (palier 2/3) via .env — ce qui rend les
    # protections sensibles OBLIGATOIRES (cf. main._validate_security_posture).
    bind_host: str = "127.0.0.1"

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8001",
    ]
    max_upload_size_mb: int = 100

    default_target_unit_system: Literal["metric", "imperial", "auto"] = "auto"

    # Cle de chiffrement Fernet (base64, >=32 chars) pour la cle Mistral stockee
    # dans AppConfig. Vide en local (stockage en clair). En prod, l'IT la fournit
    # via .env — la generer avec app.core.encryption.generate_key() (cf. .env.example).
    encryption_key: str = ""

    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai"
    mistral_chat_model: str = "mistral-small-latest"
    mistral_vision_model: str = "pixtral-12b-2409"

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

    @property
    def encryption_configured(self) -> bool:
        """Cle de chiffrement presente et assez longue pour Fernet."""
        return bool(self.encryption_key and len(self.encryption_key) >= 32)


settings = Settings()
