"""Mistral API client — sync + async, with DB-backed settings.

Ported and consolidated from legacy. UUID-aware where relevant.
"""

from __future__ import annotations

import base64
import json
import logging
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


logger = logging.getLogger(__name__)


CONFIG_KEYS = {
    "api_key":      "MISTRAL_API_KEY",
    "base_url":     "MISTRAL_BASE_URL",
    "chat_model":   "MISTRAL_CHAT_MODEL",
    "embed_model":  "MISTRAL_EMBED_MODEL",
    "vision_model": "MISTRAL_VISION_MODEL",
}

# Cles dont la valeur est chiffree au repos dans AppConfig (cf. encryption.py).
# Seul le secret Mistral est sensible ; les flags (llm_enabled, llm_last_test_ok)
# et les modeles/base_url restent en clair.
ENCRYPTED_KEYS = {"MISTRAL_API_KEY"}

# Interrupteur global IA. Stocke "true"/"false" dans AppConfig. Hors CONFIG_KEYS
# (pas un paramètre Mistral) : géré par get_llm_enabled / set_llm_enabled.
LLM_ENABLED_KEY = "llm_enabled"

# Dernier test de connexion Mistral reussi ? Cle bare dans `app_config`, defaut
# "false". Le badge LLM ne passe au vert (ON) que si la cle est configuree, le
# LLM active ET ce flag vrai. Remis a "false" des que la cle ou la base_url
# change (re-test obligatoire).
LLM_TESTED_KEY = "llm_last_test_ok"


class MistralError(RuntimeError):
    """Raised when Mistral API rejects a call or is not configured."""


def _get_secret_manager():
    """SecretManager configure depuis settings. Cle absente => chiffrement off
    (valeurs lues/ecrites en clair, mode dev/local)."""
    from app.config import settings
    from app.core.encryption import SecretManager

    if not settings.encryption_key:
        logger.warning("Encryption key not configured - secrets stored in plaintext (INSECURE)")
        return SecretManager(None)

    return SecretManager(settings.encryption_key)


def _get_config(db: Session, key: str, default: str = "") -> str:
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


def _set_config(db: Session, key: str, value: str) -> None:
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
        "api_key":      _get_config(db, CONFIG_KEYS["api_key"], defaults.mistral_api_key),
        "base_url":     _get_config(db, CONFIG_KEYS["base_url"], defaults.mistral_base_url),
        "chat_model":   _get_config(db, CONFIG_KEYS["chat_model"], defaults.mistral_chat_model),
        "embed_model":  _get_config(db, CONFIG_KEYS["embed_model"], defaults.mistral_embed_model),
        "vision_model": _get_config(db, CONFIG_KEYS["vision_model"], defaults.mistral_vision_model),
    }


def save_settings(db: Session, data: dict[str, Any]) -> None:
    invalidate_test = False
    for k, v in data.items():
        if k in CONFIG_KEYS and v is not None:
            _set_config(db, CONFIG_KEYS[k], str(v))
            if k in {"api_key", "base_url"}:
                invalidate_test = True
    # Changer la cle ou l'endpoint invalide le dernier test reussi.
    if invalidate_test:
        _set_config(db, LLM_TESTED_KEY, "false")
    db.commit()


def get_llm_enabled(db: Session) -> bool:
    """Interrupteur global IA. Défaut ON (true) si la clé n'existe pas encore.
    OFF coupe toutes les tâches confiées à Mistral ; la clé reste préservée.

    Lecture défensive : si `app_config` n'est pas encore migrée (DB neuve,
    /health appelé avant Alembic), on retombe sur le défaut ON plutôt que de
    faire planter la sonde de liveness."""
    try:
        return _get_config(db, LLM_ENABLED_KEY, "true").strip().lower() in {"1", "true", "yes"}
    except SQLAlchemyError:
        db.rollback()
        return True


def set_llm_enabled(db: Session, enabled: bool) -> None:
    # `_set_config` ne commit pas (cf. save_settings qui commit après la boucle) :
    # on commit ici pour persister le toggle.
    _set_config(db, LLM_ENABLED_KEY, "true" if enabled else "false")
    db.commit()


def get_llm_tested(db: Session) -> bool:
    """Dernier test de connexion Mistral reussi ? (defaut: false).

    Lecture defensive comme get_llm_enabled : si `app_config` n'est pas encore
    migree, on retombe sur false plutot que de faire planter /health."""
    try:
        return _get_config(db, LLM_TESTED_KEY, "false").strip().lower() in {"1", "true", "yes"}
    except SQLAlchemyError:
        db.rollback()
        return False


def set_llm_tested(db: Session, ok: bool) -> None:
    _set_config(db, LLM_TESTED_KEY, "true" if ok else "false")
    db.commit()


def requires_llm(route_name: str):
    """Decorator pour marquer une route comme exigeant le LLM.
    
    Documente à titre informatif (pour audit AACF HR4/HR7) qu'une route 
    dépend entièrement du LLM. Quand LLM est OFF, la route se comporte 
    en dégradation gracieuse (cf. chat.py, analysis.py pour l'implémentation).
    
    Usage:
        @router.post("/ask")
        @requires_llm("corpus-agent.chat.ask")
        async def ask(body: ChatAskIn, db: Session = Depends(get_db)):
            ...
    """
    def decorator(func):
        func.__requires_llm__ = True
        func.__llm_route_name__ = route_name
        return func
    return decorator
    def __init__(
        self,
        api_key: str,
        base_url: str,
        chat_model: str,
        embed_model: str,
        vision_model: str,
    ) -> None:
        if not api_key:
            raise MistralError("MISTRAL_API_KEY is not configured. Set it in Paramètres.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.vision_model = vision_model

    @classmethod
    def from_db(cls, db: Session) -> "MistralClient":
        s = get_effective_settings(db)
        return cls(
            api_key=s["api_key"],
            base_url=s["base_url"],
            chat_model=s["chat_model"],
            embed_model=s["embed_model"],
            vision_model=s["vision_model"],
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ------------- Sync API (for checks, settings test) -------------------

    def list_models(self) -> list[str]:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{self.base_url}/v1/models", headers=self._headers())
            r.raise_for_status()
            data = r.json()
            return [m.get("id", "") for m in data.get("data", [])]

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        response_format: Optional[dict[str, Any]] = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self.chat_model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]

    def chat_json(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        content = self.chat(messages, model=model, response_format={"type": "json_object"})
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content, "error": "invalid_json"}

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

    def describe_image(
        self,
        image_bytes: bytes,
        *,
        mime_type: str = "image/png",
        prompt: str = "Décris cette illustration technique en français, en 2 phrases.",
        model: Optional[str] = None,
    ) -> str:
        b64 = base64.b64encode(image_bytes).decode()
        data_url = f"data:{mime_type};base64,{b64}"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": data_url},
                ],
            }
        ]
        return self.chat(messages, model=model or self.vision_model, temperature=0.1)

    def ocr(
        self,
        image_bytes: bytes,
        *,
        mime_type: str = "image/png",
        model: Optional[str] = None,
    ) -> str:
        """OCR via l'API dédiée Mistral (`POST /v1/ocr`). Renvoie le texte
        transcrit (markdown concaténé de toutes les pages)."""
        from app.config import settings as _settings

        b64 = base64.b64encode(image_bytes).decode()
        if mime_type == "application/pdf":
            document = {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{b64}",
            }
        else:
            document = {
                "type": "image_url",
                "image_url": f"data:{mime_type};base64,{b64}",
            }
        payload = {
            "model": model or _settings.mistral_ocr_model,
            "document": document,
        }
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{self.base_url}/v1/ocr",
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        pages = data.get("pages") or []
        return "\n\n".join(
            (p.get("markdown") or "").strip()
            for p in pages
            if isinstance(p, dict)
        ).strip()

    def check_image_compliance(
        self,
        image_bytes: bytes,
        rules: list[dict[str, Any]],
        *,
        mime_type: str = "image/png",
    ) -> dict[str, Any]:
        """Pose N questions de conformite au modele vision en un seul appel.

        Retourne `{"results": [{"id", "compliant": bool, "evidence": str}, …]}`.
        Si JSON invalide, retourne `{"results": [], "error": "invalid_json", "raw": …}`.
        """
        if not rules:
            return {"results": []}
        b64 = base64.b64encode(image_bytes).decode()
        data_url = f"data:{mime_type};base64,{b64}"
        questions_block = "\n".join(
            f'- id="{r.get("id", "")}" : {r.get("question", "")}'
            for r in rules
        )
        prompt = (
            "Tu analyses une illustration technique extraite d'un document technique. "
            "Pour chacune des règles ci-dessous, indique si l'image est conforme. "
            "Si une règle ne s'applique pas à ce que montre l'image (par exemple une question sur "
            "les EPI alors qu'aucune personne n'est visible), réponds compliant=true et précise "
            '"non applicable" dans le champ evidence.\n\n'
            f"Règles à vérifier :\n{questions_block}\n\n"
            "Réponds STRICTEMENT en JSON, sans commentaire avant ou après :\n"
            '{"results": [{"id": "<id de la règle>", "compliant": true|false, '
            '"evidence": "une phrase courte en français qui justifie le verdict"}]}'
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": data_url},
                ],
            }
        ]
        content = self.chat(
            messages,
            model=self.vision_model,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {"results": [], "error": "invalid_json", "raw": content}
        if not isinstance(parsed, dict) or not isinstance(parsed.get("results"), list):
            return {"results": [], "error": "invalid_shape", "raw": content}
        return parsed

    # ------------- Async streaming (chat / SSE) ---------------------------

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
