"""Mistral API config — persisted in the `app_config` key/value table.

Falls back to env-derived defaults from `app.config.settings` when the row
is absent. Nothing is mandatory: doc-reviewer only uses Mistral for
optional LLM-assisted suggestions; if the key is empty, the rest of the
analysis pipeline still runs.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AppConfig


logger = logging.getLogger(__name__)

_KEYS = ("api_key", "base_url", "chat_model", "vision_model")
_PREFIX = "mistral."

# Cles (bare, sans prefixe) dont la valeur est chiffree au repos dans AppConfig
# (cf. encryption.py). Seul le secret Mistral est sensible ; base_url et modeles
# restent en clair.
ENCRYPTED_KEYS = {"api_key"}


def _get_secret_manager():  # type: ignore[no-untyped-def]
    """SecretManager configure depuis settings. Cle absente => chiffrement off
    (valeurs lues/ecrites en clair, mode dev/local)."""
    from app.core.encryption import SecretManager

    if not settings.encryption_key:
        logger.warning("Encryption key not configured - secrets stored in plaintext (INSECURE)")
        return SecretManager(None)
    return SecretManager(settings.encryption_key)


def _get(db: Session, key: str) -> str | None:
    row = db.get(AppConfig, _PREFIX + key)
    if row is None or not row.value:
        return None
    if key in ENCRYPTED_KEYS:
        try:
            return _get_secret_manager().decrypt(row.value)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to decrypt %s: %s", key, e)
            return None
    return row.value


def _set(db: Session, key: str, value: str) -> None:
    if key in ENCRYPTED_KEYS and value:
        value = _get_secret_manager().encrypt(value)
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


_LLM_ENABLED_KEY = "llm_enabled"


def get_llm_enabled(db: Session) -> bool:
    try:
        row = db.get(AppConfig, _LLM_ENABLED_KEY)
    except SQLAlchemyError:
        db.rollback()
        return True
    if row is None or not row.value:
        return True  # defaut active
    return row.value.strip().lower() in {"1", "true", "yes"}


def set_llm_enabled(db: Session, enabled: bool) -> None:
    value = "true" if enabled else "false"
    row = db.get(AppConfig, _LLM_ENABLED_KEY)
    if row is None:
        db.add(AppConfig(key=_LLM_ENABLED_KEY, value=value))
    else:
        row.value = value
    db.commit()


def save(db: Session, payload: dict[str, str]) -> None:
    invalidate_test = False
    for k in _KEYS:
        if k in payload:
            _set(db, k, payload[k])
            if k in {"api_key", "base_url"}:
                invalidate_test = True
    # Changing the key or endpoint invalidates the last successful test
    # (a re-test is mandatory before the badge can go green again).
    # NB: `_set` prefixes the key; the tested flag is a bare key, so write it
    # directly rather than through `_set`.
    if invalidate_test:
        row = db.get(AppConfig, _LLM_TESTED_KEY)
        if row is None:
            db.add(AppConfig(key=_LLM_TESTED_KEY, value="false"))
        else:
            row.value = "false"
    db.commit()


# ---- Last Mistral connection test result -----------------------------------
# `true` only after `/settings/mistral/test` succeeded. The LLM badge turns
# green (ON) only when the key is configured, the LLM switch is on AND this
# flag is true. Reset to "false" whenever the api_key / base_url changes.

_LLM_TESTED_KEY = "llm_last_test_ok"


def get_llm_tested(db: Session) -> bool:
    try:
        row = db.get(AppConfig, _LLM_TESTED_KEY)
    except SQLAlchemyError:
        db.rollback()
        return False
    if row is None or not row.value:
        return False
    return row.value.strip().lower() in {"1", "true", "yes"}


def set_llm_tested(db: Session, ok: bool) -> None:
    value = "true" if ok else "false"
    row = db.get(AppConfig, _LLM_TESTED_KEY)
    if row is None:
        db.add(AppConfig(key=_LLM_TESTED_KEY, value=value))
    else:
        row.value = value
    db.commit()


# ---- Fiabilisation LLM (verification adversariale + feedback global) -------
# Config runtime de la pile de fiabilisation portee de word-reviewer. Stockee
# en clair dans app_config. Defauts calques sur word-reviewer.

_VERIFY_ENABLED_KEY = "llm.verify_enabled"
_VERIFY_PASSES_KEY = "llm.verify_passes"
_MAX_CALLS_KEY = "llm.max_calls"
_FEEDBACK_ENABLED_KEY = "llm.feedback_enabled"

_VERIFY_PASSES_DEFAULT = 3
_MAX_CALLS_DEFAULT = 400


def _get_bool(db: Session, key: str, default: bool) -> bool:
    try:
        row = db.get(AppConfig, key)
    except SQLAlchemyError:
        db.rollback()
        return default
    if row is None or not row.value:
        return default
    return row.value.strip().lower() in {"1", "true", "yes"}


def _set_bool(db: Session, key: str, value: bool) -> None:
    text = "true" if value else "false"
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=text))
    else:
        row.value = text
    db.commit()


def _get_int(db: Session, key: str, default: int, *, lo: int, hi: int) -> int:
    try:
        row = db.get(AppConfig, key)
    except SQLAlchemyError:
        db.rollback()
        return default
    if row is None or not row.value:
        return default
    try:
        value = int(row.value.strip())
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, value))


def _set_int(db: Session, key: str, value: int, *, lo: int, hi: int) -> None:
    clamped = max(lo, min(hi, int(value)))
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=str(clamped)))
    else:
        row.value = str(clamped)
    db.commit()


def get_verify_enabled(db: Session) -> bool:
    return _get_bool(db, _VERIFY_ENABLED_KEY, True)


def set_verify_enabled(db: Session, enabled: bool) -> None:
    _set_bool(db, _VERIFY_ENABLED_KEY, enabled)


def get_verify_passes(db: Session) -> int:
    return _get_int(db, _VERIFY_PASSES_KEY, _VERIFY_PASSES_DEFAULT, lo=1, hi=5)


def set_verify_passes(db: Session, passes: int) -> None:
    _set_int(db, _VERIFY_PASSES_KEY, passes, lo=1, hi=5)


def get_llm_max_calls(db: Session) -> int:
    return _get_int(db, _MAX_CALLS_KEY, _MAX_CALLS_DEFAULT, lo=0, hi=5000)


def set_llm_max_calls(db: Session, max_calls: int) -> None:
    _set_int(db, _MAX_CALLS_KEY, max_calls, lo=0, hi=5000)


def get_feedback_enabled(db: Session) -> bool:
    return _get_bool(db, _FEEDBACK_ENABLED_KEY, True)


def set_feedback_enabled(db: Session, enabled: bool) -> None:
    _set_bool(db, _FEEDBACK_ENABLED_KEY, enabled)


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
