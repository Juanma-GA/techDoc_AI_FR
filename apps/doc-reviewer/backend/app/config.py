"""Application settings — loaded from env / .env via pydantic-settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Listes lues depuis l'environnement au format « a,b,c » (cf. .env.example) :
# `NoDecode` empeche pydantic-settings de les parser comme du JSON (sinon
# CORS_ORIGINS=http://x,http://y faisait echouer le demarrage).
CsvList = Annotated[list[str], NoDecode]


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "doc-reviewer"
    app_version: str = "2.0.0"
    log_level: str = "INFO"

    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'doc-reviewer.db'}"
    storage_dir: str = str(BASE_DIR / "data" / "storage")

    # Hote de bind uvicorn. Palier 1 (local) : 127.0.0.1. L'IT le passe a une
    # valeur exposee au deploiement (palier 2/3) via .env — ce qui rend les
    # protections sensibles OBLIGATOIRES (cf. main._validate_security_posture).
    bind_host: str = "127.0.0.1"

    # Noms d'hote (en-tete Host) acceptes EN PLUS des hotes de bouclage
    # (localhost, 127.0.0.1, [::1]). Vide en local : toute requete dont le Host
    # n'est pas local est refusee (anti DNS-rebinding, cf. core.request_guard).
    # Liste separee par des virgules, ports optionnels ("docrev.example:443").
    allowed_hosts: CsvList = []

    # L'application n'a AUCUNE authentification integree. Exposer l'API au-dela
    # du poste (bind non local, ou acces via un reverse proxy) n'est autorise
    # que si l'IT atteste qu'un reverse proxy AUTHENTIFIANT (SSO) est place
    # devant. Sans cette attestation : refus au demarrage (bind expose) et
    # refus a l'execution de toute requete relayee par un proxy.
    behind_auth_proxy: bool = False

    cors_origins: CsvList = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8003",
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
    mistral_vision_model: str = "mistral-medium-3-5"
    # Points d'acces LLM autorises (https uniquement). La cle API n'est JAMAIS
    # envoyee a une URL hors de cette liste : une base_url modifiable depuis
    # l'UI permettait sinon d'exfiltrer la cle et le texte des documents vers
    # un hote arbitraire. L'IT etend la liste via .env si un endpoint prive
    # (compatible Mistral) est approuve.
    mistral_allowed_base_urls: CsvList = ["https://api.mistral.ai"]

    # Moteur des conversions .doc/.docx/PDF. "auto" : Microsoft Word, puis
    # LibreOffice s'il est installe ; "word" ou "libreoffice" : ce moteur seul.
    office_converter: Literal["auto", "word", "libreoffice"] = "auto"
    # Identifiant (GUID) de l'etiquette de confidentialite Microsoft Purview
    # posee sur un .docx produit par conversion quand le document n'en porte
    # pas deja une. Obligatoire sur un poste ou l'etiquetage est impose (Word
    # refuse sinon d'enregistrer le .docx). Valeur choisie par l'IT.
    word_sensitivity_label_id: str = ""
    # Delai au-dela duquel une conversion Word est consideree bloquee (boite de
    # dialogue invisible) : l'instance WINWORD de la conversion est arretee.
    word_convert_timeout_seconds: int = 180

    @field_validator(
        "cors_origins", "allowed_hosts", "mistral_allowed_base_urls", mode="before"
    )
    @classmethod
    def _parse_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            raw = v.strip()
            # Compatibilite : la forme JSON (["a","b"]) reste acceptee.
            if raw.startswith("["):
                return json.loads(raw)
            return [s.strip() for s in raw.split(",") if s.strip()]
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def debug(self) -> bool:
        """Enable FastAPI debug mode only when detailed logs are requested."""
        return self.log_level.strip().upper() == "DEBUG"

    @property
    def llm_configured(self) -> bool:
        return bool(self.mistral_api_key)

    @property
    def encryption_configured(self) -> bool:
        """Cle de chiffrement presente et assez longue pour Fernet."""
        return bool(self.encryption_key and len(self.encryption_key) >= 32)


settings = Settings()
