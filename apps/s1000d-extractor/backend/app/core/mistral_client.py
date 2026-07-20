"""Client Mistral minimal - httpx async (streaming) + httpx sync (embeddings).

Pas de SDK Mistral. La configuration runtime est lue dans la table `app_config`
avec fallback sur `app.config.settings` (qui lit le `.env`).
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import AppConfig

logger = logging.getLogger(__name__)

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass


CONFIG_KEYS = {
    "api_key": "MISTRAL_API_KEY",
    "base_url": "MISTRAL_BASE_URL",
    "chat_model": "MISTRAL_CHAT_MODEL",
    "embed_model": "MISTRAL_EMBED_MODEL",
    "ocr_model": "MISTRAL_OCR_MODEL",
}

# Cles dont la valeur est chiffree au repos dans AppConfig (cf. encryption.py).
# Seul le secret Mistral est sensible ; flags et modeles restent en clair.
ENCRYPTED_KEYS = {"MISTRAL_API_KEY"}

# Interrupteur global LLM (standard). Cle bare dans `app_config`, defaut "true".
# OFF = on saute la tache confiee a l'IA (fallback gracieux), la cle Mistral est conservee.
LLM_ENABLED_KEY = "llm_enabled"

# Dernier test de connexion Mistral reussi ? (standard). Cle bare dans
# `app_config`, defaut "false". Le badge LLM ne passe au vert (ON) que si la cle
# est configuree, le LLM active ET ce flag vrai. Remis a "false" des que la cle
# ou la base_url change (re-test obligatoire).
LLM_TESTED_KEY = "llm_last_test_ok"


class MistralError(RuntimeError):
    """Levee si Mistral n'est pas configure ou rejette un appel."""


def _get_secret_manager():  # type: ignore[no-untyped-def]
    """SecretManager configure depuis settings. Cle absente => chiffrement off
    (valeurs lues/ecrites en clair, mode dev/local)."""
    from app.config import settings
    from app.core.encryption import SecretManager

    if not settings.encryption_key:
        logger.warning("Encryption key not configured - secrets stored in plaintext (INSECURE)")
        return SecretManager(None)
    return SecretManager(settings.encryption_key)


def _read_config(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppConfig, key)
    if not row or not row.value:
        return default
    if key in ENCRYPTED_KEYS:
        try:
            return _get_secret_manager().decrypt(row.value)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to decrypt %s: %s", key, e)
            return default
    return row.value


def _write_config(db: Session, key: str, value: str) -> None:
    if key in ENCRYPTED_KEYS and value:
        try:
            value = _get_secret_manager().encrypt(value)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to encrypt %s: %s", key, e)
            raise MistralError(f"Encryption failed: {e}") from e
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=value))
    else:
        row.value = value


def get_effective_settings(db: Session) -> dict[str, str]:
    from app.config import settings as defaults

    return {
        "api_key": _read_config(db, CONFIG_KEYS["api_key"], defaults.mistral_api_key),
        "base_url": _read_config(db, CONFIG_KEYS["base_url"], defaults.mistral_base_url),
        "chat_model": _read_config(db, CONFIG_KEYS["chat_model"], defaults.mistral_chat_model),
        "embed_model": _read_config(
            db, CONFIG_KEYS["embed_model"], getattr(defaults, "mistral_embed_model", "mistral-embed")
        ),
        "ocr_model": _read_config(
            db, CONFIG_KEYS["ocr_model"], getattr(defaults, "mistral_ocr_model", "mistral-ocr-latest")
        ),
    }


def save_settings(db: Session, data: dict[str, Any]) -> None:
    invalidate_test = False
    for k, v in data.items():
        if k in CONFIG_KEYS and v is not None:
            _write_config(db, CONFIG_KEYS[k], str(v))
            if k in {"api_key", "base_url"}:
                invalidate_test = True
    # Changer la cle ou l'endpoint invalide le dernier test reussi.
    if invalidate_test:
        _write_config(db, LLM_TESTED_KEY, "false")
    db.commit()


def get_llm_enabled(db: Session) -> bool:
    """Etat de l'interrupteur LLM (defaut: active)."""
    try:
        return _read_config(db, LLM_ENABLED_KEY, "true").strip().lower() in {"1", "true", "yes"}
    except SQLAlchemyError:
        db.rollback()
        return True


def set_llm_enabled(db: Session, enabled: bool) -> None:
    _write_config(db, LLM_ENABLED_KEY, "true" if enabled else "false")
    db.commit()


def get_llm_tested(db: Session) -> bool:
    """Dernier test de connexion Mistral reussi ? (defaut: false)."""
    try:
        return _read_config(db, LLM_TESTED_KEY, "false").strip().lower() in {"1", "true", "yes"}
    except SQLAlchemyError:
        db.rollback()
        return False


def set_llm_tested(db: Session, ok: bool) -> None:
    _write_config(db, LLM_TESTED_KEY, "true" if ok else "false")
    db.commit()


class MistralClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        chat_model: str,
        embed_model: str,
        ocr_model: str = "mistral-ocr-latest",
    ) -> None:
        if not api_key:
            raise MistralError("MISTRAL_API_KEY non configuree. Renseigne-la dans Parametres.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.ocr_model = ocr_model

    @classmethod
    def from_db(cls, db: Session) -> MistralClient:
        s = get_effective_settings(db)
        return cls(
            api_key=s["api_key"],
            base_url=s["base_url"],
            chat_model=s["chat_model"],
            embed_model=s["embed_model"],
            ocr_model=s.get("ocr_model", "mistral-ocr-latest"),
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def list_models(self) -> list[str]:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{self.base_url}/v1/models", headers=self._headers())
            r.raise_for_status()
            data = r.json()
            return [m.get("id", "") for m in data.get("data", [])]

    def ocr_pdf(self, pdf_bytes: bytes, *, timeout: float = 180.0) -> list[str]:
        """OCR d'un PDF via l'API dediee Mistral (`POST /v1/ocr`).

        Renvoie le markdown transcrit, une entree par page. Utilise en repli
        quand un PDF n'a pas de couche texte (scanne).
        """
        b64 = base64.b64encode(pdf_bytes).decode()
        payload = {
            "model": self.ocr_model,
            "document": {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{b64}",
            },
        }
        with httpx.Client(timeout=timeout) as client:
            r = client.post(f"{self.base_url}/v1/ocr", headers=self._headers(), json=payload)
            r.raise_for_status()
            data = r.json()
        pages = data.get("pages") or []
        return [(p.get("markdown") or "").strip() for p in pages if isinstance(p, dict)]

    def embed(self, inputs: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{self.base_url}/v1/embeddings",
                headers=self._headers(),
                json={"model": self.embed_model, "input": inputs},
            )
            r.raise_for_status()
            data = r.json()
            return [item["embedding"] for item in data["data"]]

    def chat_json(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Appel chat non streame, sortie forcee en JSON object.

        Utilise par la classification de contexte (descriptif / procedural)
        et la segmentation de prose en etapes. Leve `MistralError` si la
        reponse n'est pas du JSON valide.
        """
        payload = {
            "model": model or self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        choices = data.get("choices") or []
        if not choices:
            raise MistralError("Reponse Mistral vide.")
        content = (choices[0].get("message") or {}).get("content") or ""
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            raise MistralError(f"Reponse non-JSON : {e}") from e
        if not isinstance(parsed, dict):
            raise MistralError("Reponse JSON n'est pas un objet.")
        return parsed

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model or self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        obj = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta
