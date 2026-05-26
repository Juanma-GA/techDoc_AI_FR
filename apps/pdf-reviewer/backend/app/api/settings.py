"""GET/POST /api/v1/settings/mistral + POST /settings/mistral/test."""

from __future__ import annotations

import structlog
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.checks.s1000d_checks import S1000D_BUILTIN_RULES
from app.core.mistral_settings import (
    get_ai_custom_prompt,
    get_disabled_s1000d,
    get_effective,
    get_vision_enabled,
    save,
    set_ai_custom_prompt,
    set_disabled_s1000d,
    set_vision_enabled,
)
from app.db.session import get_db
from app.schemas import MistralSettingsIn, MistralSettingsOut, TestConnectionOut

# Inject the OS trust store into Python's ssl module so corporate CAs and
# transparent SSL proxies work without `pip install certifi --upgrade` games.
# Idempotent + best-effort: silently skip if the package is missing or the
# runtime doesn't support it.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass


logger = structlog.get_logger(__name__)


router = APIRouter(prefix="/settings", tags=["settings"])


def _build_out(db: Session) -> MistralSettingsOut:
    s = get_effective(db)
    key = s["api_key"] or ""
    preview = (key[:4] + "…" + key[-4:]) if len(key) > 10 else ("•" * len(key) if key else "")
    return MistralSettingsOut(
        api_key_set=bool(key),
        api_key_preview=preview,
        base_url=s["base_url"],
        chat_model=s["chat_model"],
        vision_model=s.get("vision_model", "pixtral-12b-2409"),
        vision_enabled=get_vision_enabled(db),
    )


@router.get("/mistral", response_model=MistralSettingsOut)
def get_mistral_settings(db: Session = Depends(get_db)) -> MistralSettingsOut:
    return _build_out(db)


@router.post("/mistral", response_model=MistralSettingsOut)
def update_mistral_settings(
    body: MistralSettingsIn,
    db: Session = Depends(get_db),
) -> MistralSettingsOut:
    payload = body.model_dump()
    # Empty api_key in the request means "keep the current one".
    if not payload.get("api_key"):
        payload.pop("api_key", None)
    # `vision_enabled` is stored separately (boolean flag, not in Mistral
    # client config). Pop it before delegating to `save()`.
    vision_enabled = payload.pop("vision_enabled", None)
    save(db, payload)
    if vision_enabled is not None:
        set_vision_enabled(db, bool(vision_enabled))
    return _build_out(db)


class VisionToggleIn(BaseModel):
    enabled: bool


@router.post("/vision")
def toggle_vision(body: VisionToggleIn, db: Session = Depends(get_db)) -> dict:
    """Standalone endpoint to toggle the vision pipeline without
    re-sending the whole Mistral payload."""
    set_vision_enabled(db, body.enabled)
    return {"enabled": get_vision_enabled(db)}


@router.post("/mistral/test", response_model=TestConnectionOut)
def test_mistral_connection(db: Session = Depends(get_db)) -> TestConnectionOut:
    s = get_effective(db)
    if not s["api_key"]:
        return TestConnectionOut(ok=False, message="Aucune clé API configurée.", models=[])
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                f"{s['base_url'].rstrip('/')}/v1/models",
                headers={"Authorization": f"Bearer {s['api_key']}"},
            )
        if r.status_code != 200:
            return TestConnectionOut(
                ok=False,
                message=f"HTTP {r.status_code} — {r.text[:200]}",
                models=[],
            )
        data = r.json() or {}
        ids = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
        return TestConnectionOut(
            ok=True,
            message=f"{len(ids)} modèle(s) accessible(s).",
            models=ids[:50],
        )
    except Exception as exc:  # noqa: BLE001
        # Catch broad — Mistral test must never raise a 500 to the UI; any
        # network/SSL/proxy/parsing problem is reported as `ok=false`.
        logger.warning("mistral_test_failed", error=type(exc).__name__, message=str(exc))
        return TestConnectionOut(
            ok=False,
            message=f"{type(exc).__name__}: {exc}",
            models=[],
        )


# ---- S1000D built-in rules ----------------------------------------------


class S1000DToggleIn(BaseModel):
    code: str
    enabled: bool


@router.get("/s1000d")
def get_s1000d_settings(db: Session = Depends(get_db)) -> dict:
    return {
        "rules": S1000D_BUILTIN_RULES,
        "disabled_codes": get_disabled_s1000d(db),
    }


@router.post("/s1000d/toggle")
def toggle_s1000d_rule(body: S1000DToggleIn, db: Session = Depends(get_db)) -> dict:
    valid_codes = {r["code"] for r in S1000D_BUILTIN_RULES}
    if body.code not in valid_codes:
        from app.core.errors import AppError

        raise AppError(
            "S1000D_CODE_UNKNOWN",
            f"Code S1000D inconnu : {body.code}",
            status_code=400,
        )
    disabled = set(get_disabled_s1000d(db))
    if body.enabled:
        disabled.discard(body.code)
    else:
        disabled.add(body.code)
    set_disabled_s1000d(db, list(disabled))
    return {
        "rules": S1000D_BUILTIN_RULES,
        "disabled_codes": sorted(disabled),
    }


# ---- AI free-text guidelines ---------------------------------------------


class AiPromptIn(BaseModel):
    prompt: str = ""


@router.get("/ai-prompt")
def get_ai_prompt(db: Session = Depends(get_db)) -> dict:
    return {"prompt": get_ai_custom_prompt(db)}


@router.post("/ai-prompt")
def update_ai_prompt(body: AiPromptIn, db: Session = Depends(get_db)) -> dict:
    set_ai_custom_prompt(db, body.prompt)
    return {"prompt": get_ai_custom_prompt(db)}
