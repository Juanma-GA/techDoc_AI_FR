"""GET /api/v1/health — liveness + dependency probes (db, llm)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.mistral_client import get_effective_settings, get_llm_enabled, get_llm_tested
from app.db.session import get_db


router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, Any]:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        db_status = f"error: {exc.__class__.__name__}"

    # Vert (ON) seulement si: cle effective (DB ou .env) presente + dernier test
    # reussi + LLM active. Sinon: disabled / not_configured / untested.
    if not get_llm_enabled(db):
        llm_status = "disabled"
    elif not get_effective_settings(db)["api_key"]:
        llm_status = "not_configured"
    elif not get_llm_tested(db):
        llm_status = "untested"
    else:
        llm_status = "ok"

    overall = "ok" if db_status == "ok" else "degraded"

    return {
        "status": overall,
        "version": settings.app_version,
        "db": db_status,
        "llm": llm_status,
    }
