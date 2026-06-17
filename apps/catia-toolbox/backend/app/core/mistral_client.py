"""Client Mistral minimal - httpx async (streaming) + httpx sync (embeddings).

Pas de SDK Mistral. La configuration runtime est lue dans la table `app_config`
avec fallback sur `app.config.settings` (qui lit le `.env`).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import AppConfig


try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass


CONFIG_KEYS = {
    "api_key": "MISTRAL_API_KEY",
    "base_url": "MISTRAL_BASE_URL",
    "chat_model": "MISTRAL_CHAT_MODEL",
    "embed_model": "MISTRAL_EMBED_MODEL",
}

# Interrupteur global LLM (standard). Cle bare dans `app_config`, defaut "true".
# OFF = on saute la tache confiee a l'IA (fallback gracieux), la cle Mistral est conservee.
LLM_ENABLED_KEY = "llm_enabled"


class MistralError(RuntimeError):
    """Levee si Mistral n'est pas configure ou rejette un appel."""


def _read_config(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppConfig, key)
    return row.value if row and row.value else default


def _write_config(db: Session, key: str, value: str) -> None:
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
    }


def save_settings(db: Session, data: dict[str, Any]) -> None:
    for k, v in data.items():
        if k in CONFIG_KEYS and v is not None:
            _write_config(db, CONFIG_KEYS[k], str(v))
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


class MistralClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        chat_model: str,
        embed_model: str,
    ) -> None:
        if not api_key:
            raise MistralError("MISTRAL_API_KEY non configuree. Renseigne-la dans Parametres.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model

    @classmethod
    def from_db(cls, db: Session) -> "MistralClient":
        s = get_effective_settings(db)
        return cls(
            api_key=s["api_key"],
            base_url=s["base_url"],
            chat_model=s["chat_model"],
            embed_model=s["embed_model"],
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

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
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
