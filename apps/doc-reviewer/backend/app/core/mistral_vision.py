"""Mistral multimodal vision helpers — ported from `apps/corpus`.

Two entry points :

- `describe_image(db, image_bytes)` returns a short French description
  of the technical illustration. Used to compare against a caption.
- `check_figure_compliance(db, image_bytes, rules)` runs a structured
  compliance check : the LLM answers a YES/NO + evidence per rule
  question in a single multimodal call.

Errors are raised as `AppError` so the analyse pipeline can degrade
gracefully (Mistral down -> suggestion skipped, not run-wide failure).
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx
import structlog
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.mistral_settings import get_endpoint, get_llm_enabled

# Inject the OS trust store — same trick used by the chat client so
# corporate SSL proxies don't sink the multimodal call.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass


logger = structlog.get_logger(__name__)


_TIMEOUT_S = 45.0
_MAX_BYTES = 4 * 1024 * 1024  # 4 MB per image


def _extract_first_json_object(text: str) -> str | None:
    """Robust JSON extraction — handles ```json fences, prose preamble."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i, c in enumerate(text[start:], start=start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _call_mistral_vision(db: Session, messages: list[dict], *, response_format: dict | None = None) -> str:
    if not get_llm_enabled(db):
        raise AppError(
            "LLM_DISABLED",
            "Les analyses IA sont desactivees dans Parametres.",
            status_code=400,
        )
    s = get_endpoint(db)
    if not s["api_key"]:
        raise AppError(
            "MISTRAL_NOT_CONFIGURED",
            "Configurez la clé API Mistral dans Paramètres pour activer la vision.",
            status_code=400,
        )
    model = s.get("vision_model") or "mistral-medium-3-5"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    try:
        logger.debug(
            "llm_request",
            provider="mistral",
            endpoint="chat/completions",
            model=payload["model"],
        )
        with httpx.Client(timeout=_TIMEOUT_S, follow_redirects=False) as client:
            r = client.post(
                f"{s['base_url']}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {s['api_key']}",
                    "Content-Type": "application/json",
                },
                content=json.dumps(payload),
            )
        logger.debug(
            "llm_response",
            provider="mistral",
            endpoint="chat/completions",
            model=payload["model"],
            status_code=r.status_code,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("vision_network_error", error=type(exc).__name__)
        raise AppError(
            "VISION_CALL_FAILED",
            f"Échec d'appel Mistral (vision) : {type(exc).__name__}",
            status_code=502,
        ) from exc
    if r.status_code != 200:
        raise AppError(
            "VISION_CALL_FAILED",
            f"Mistral vision a renvoyé HTTP {r.status_code}.",
            status_code=502,
            detail={"body": r.text[:300]},
        )
    try:
        data = r.json()
        return data["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError) as exc:
        raise AppError(
            "VISION_CALL_FAILED",
            "Réponse Mistral vision non interprétable.",
            status_code=502,
        ) from exc


def _image_too_large(image_bytes: bytes) -> bool:
    return len(image_bytes) > _MAX_BYTES


def describe_image(
    db: Session,
    image_bytes: bytes,
    *,
    mime_type: str = "image/png",
    prompt: str = (
        "Décris cette illustration technique en français, en 1 à 2 phrases. "
        "Sois précis sur les éléments visibles (composants, outils, opération)."
    ),
) -> str:
    """Return a short French description of the technical illustration.
    Raises `AppError(VISION_CALL_FAILED)` on Mistral failure."""
    if _image_too_large(image_bytes):
        raise AppError(
            "VISION_IMAGE_TOO_LARGE",
            f"Image trop volumineuse ({len(image_bytes)} octets, max {_MAX_BYTES}).",
            status_code=413,
        )
    b64 = base64.b64encode(image_bytes).decode()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:{mime_type};base64,{b64}"},
            ],
        }
    ]
    return _call_mistral_vision(db, messages).strip()


def check_figure_compliance(
    db: Session,
    image_bytes: bytes,
    rules: list[dict[str, Any]],
    *,
    mime_type: str = "image/png",
) -> dict[str, Any]:
    """Ask the Mistral multimodal model N yes/no compliance questions about an image in a
    single multimodal call. Returns the parsed JSON
    `{"results": [{"id", "compliant": bool, "evidence": str}, …]}`.

    A non-applicable rule should be answered `compliant=true` with
    evidence «non applicable» — that's the convention the prompt makes
    explicit. Invalid responses return an empty results list."""
    if not rules:
        return {"results": []}
    if _image_too_large(image_bytes):
        raise AppError(
            "VISION_IMAGE_TOO_LARGE",
            f"Image trop volumineuse ({len(image_bytes)} octets, max {_MAX_BYTES}).",
            status_code=413,
        )

    b64 = base64.b64encode(image_bytes).decode()
    questions = "\n".join(
        f'- id="{r.get("id", "")}" : {r.get("question", "")}'
        for r in rules
        if isinstance(r, dict)
    )
    prompt = (
        "Tu analyses une illustration technique extraite d'une publication de "
        "maintenance aéronautique. Pour chacune des règles ci-dessous, indique "
        "si l'image est conforme. Si une règle ne s'applique pas à ce que "
        "montre l'image (par exemple une question sur les EPI alors qu'aucune "
        "personne n'est visible), réponds compliant=true et précise « non "
        "applicable » dans le champ evidence.\n\n"
        f"Règles à vérifier :\n{questions}\n\n"
        'Réponds STRICTEMENT en JSON sans texte avant ou après : '
        '{"results": [{"id": "<id>", "compliant": true|false, '
        '"evidence": "phrase courte en français"}]}'
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:{mime_type};base64,{b64}"},
            ],
        }
    ]
    content = _call_mistral_vision(db, messages, response_format={"type": "json_object"})
    json_text = _extract_first_json_object(content) or content
    try:
        parsed = json.loads(json_text)
    except (ValueError, TypeError):
        raise AppError(
            "VISION_RESPONSE_INVALID",
            "La réponse vision est inexploitable; cette partie de l'analyse est incomplète.",
            status_code=502,
        )
    if not isinstance(parsed, dict) or not isinstance(parsed.get("results"), list):
        raise AppError(
            "VISION_RESPONSE_INVALID",
            "La réponse vision est inexploitable; cette partie de l'analyse est incomplète.",
            status_code=502,
        )
    return parsed
