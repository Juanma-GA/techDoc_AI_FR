"""GET /api/v1/health — liveness + dependency probes (db, llm)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db


router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, Any]:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        db_status = f"error: {exc.__class__.__name__}"

    llm_status = "configured" if settings.llm_configured else "not_configured"

    overall = "ok" if db_status == "ok" else "degraded"

    return {
        "status": overall,
        "version": settings.app_version,
        "db": db_status,
        "llm": llm_status,
    }
