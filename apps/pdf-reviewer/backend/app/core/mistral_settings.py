"""Mistral API config — persisted in the `app_config` key/value table.

Falls back to env-derived defaults from `app.config.settings` when the row
is absent. Nothing is mandatory: pdf-reviewer only uses Mistral for
optional LLM-assisted suggestions; if the key is empty, the rest of the
analysis pipeline still runs.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AppConfig


_KEYS = ("api_key", "base_url", "chat_model", "vision_model")
_PREFIX = "mistral."


def _get(db: Session, key: str) -> str | None:
    row = db.get(AppConfig, _PREFIX + key)
    return row.value if row else None


def _set(db: Session, key: str, value: str) -> None:
    row = db.get(AppConfig, _PREFIX + key)
    if row is None:
        db.add(AppConfig(key=_PREFIX + key, value=value))
    else:
        row.value = value


def get_effective(db: Session) -> dict[str, str]:
    """Read the persisted overrides, falling back to env defaults."""
    defaults = {
        "api_key": settings.mistral_api_key,
        "base_url": settings.mistral_base_url,
        "chat_model": settings.mistral_chat_model,
        "vision_model": settings.mistral_vision_model,
    }
    out: dict[str, str] = {}
    for k in _KEYS:
        v = _get(db, k)
        out[k] = v if v is not None else defaults[k]
    return out


_VISION_ENABLED_KEY = "vision.enabled"


def get_vision_enabled(db: Session) -> bool:
    row = db.get(AppConfig, _VISION_ENABLED_KEY)
    return bool(row and row.value and row.value.lower() in {"1", "true", "yes"})


def set_vision_enabled(db: Session, enabled: bool) -> None:
    value = "true" if enabled else "false"
    row = db.get(AppConfig, _VISION_ENABLED_KEY)
    if row is None:
        db.add(AppConfig(key=_VISION_ENABLED_KEY, value=value))
    else:
        row.value = value
    db.commit()


def save(db: Session, payload: dict[str, str]) -> None:
    for k in _KEYS:
        if k in payload:
            _set(db, k, payload[k])
    db.commit()


# ---- S1000D toggle ---------------------------------------------------------
# Stored as a CSV string under `s1000d.disabled_codes` in `app_config`.

_S1000D_KEY = "s1000d.disabled_codes"


def get_disabled_s1000d(db: Session) -> list[str]:
    row = db.get(AppConfig, _S1000D_KEY)
    if row is None or not row.value:
        return []
    return [c.strip().upper() for c in row.value.split(",") if c.strip()]


def set_disabled_s1000d(db: Session, codes: list[str]) -> None:
    cleaned = sorted({c.strip().upper() for c in codes if c.strip()})
    csv = ",".join(cleaned)
    row = db.get(AppConfig, _S1000D_KEY)
    if row is None:
        db.add(AppConfig(key=_S1000D_KEY, value=csv))
    else:
        row.value = csv
    db.commit()


# ---- Free-text AI guidelines ----------------------------------------------
# A user-authored prompt addendum that drives the `AI_CUSTOM` pass —
# Mistral scans every page text with these guidelines and proposes
# corrections in natural language. Stored as plain text in app_config.

_AI_PROMPT_KEY = "ai.custom_prompt"


def get_ai_custom_prompt(db: Session) -> str:
    row = db.get(AppConfig, _AI_PROMPT_KEY)
    return (row.value if row else "") or ""


def set_ai_custom_prompt(db: Session, text: str) -> None:
    cleaned = (text or "").strip()
    row = db.get(AppConfig, _AI_PROMPT_KEY)
    if row is None:
        db.add(AppConfig(key=_AI_PROMPT_KEY, value=cleaned))
    else:
        row.value = cleaned
    db.commit()
