"""GET /api/v1/health — liveness + db probe."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.mistral_settings import get_effective, get_llm_enabled, get_llm_tested
from app.db.session import get_db


router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, Any]:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        db_status = f"error: {exc.__class__.__name__}"

    overall = "ok" if db_status == "ok" else "degraded"

    # Green (configured = ON) only when: effective key present (DB or .env) +
    # last test succeeded + LLM switch on. Otherwise: disabled /
    # not_configured (no key) / untested (key present but test not passed).
    if not get_llm_enabled(db):
        llm = "disabled"
    elif not get_effective(db)["api_key"]:
        llm = "not_configured"
    elif not get_llm_tested(db):
        llm = "untested"
    else:
        # Regle #14 : l'etat vert est "ok" (et non "configured") — c'est la
        # valeur attendue par le badge LLM du front (lib/api LlmState).
        llm = "ok"

    return {
        "status": overall,
        "version": settings.app_version,
        "db": db_status,
        "llm": llm,
    }
