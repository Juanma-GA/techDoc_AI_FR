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

    app_name: str = "doc-writer"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'doc-writer.db'}"
    storage_dir: str = str(BASE_DIR / "data" / "storage")

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8002",
        "http://127.0.0.1:8002",
    ]
    max_upload_size_mb: int = 50

    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai"
    mistral_chat_model: str = "mistral-small-latest"
    mistral_embed_model: str = "mistral-embed"
    # Lecture des PDF par Mistral (des qu'une cle API est configuree), en 3
    # niveaux de repli automatique :
    #   1. VISION (modele multimodal) : pages rendues en images et interpretees
    #      -> lit AUSSI le graphique (drapeaux, jauges/barres de niveau, etoiles)
    #      que l'OCR texte ne peut pas comprendre. Moteur par defaut.
    #   2. OCR document (/v1/ocr) : texte + structure (colonnes, tableaux).
    #   3. Extraction LOCALE (couche texte PyMuPDF + Tesseract).
    mistral_vision_model: str = "mistral-small-latest"
    mistral_ocr_model: str = "mistral-ocr-latest"

    # Repli LOCAL (quand Mistral indisponible) : couche texte PyMuPDF + OCR
    # Tesseract page par page sur les pages sans texte. Tesseract est un binaire
    # systeme externe (cf. README) ; absent -> page scannee vide, pas de crash.
    # `pdf_ocr_tessdata` pointe le dossier tessdata si TESSDATA_PREFIX absent.
    pdf_ocr_enabled: bool = True
    pdf_ocr_lang: str = "fra+eng"
    pdf_ocr_dpi: int = 300
    pdf_ocr_tessdata: str = ""

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
