"""GET /api/v1/health — liveness + dependency status."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.core.mistral_client import get_llm_enabled
from app.db.session import get_db
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(db: Session = Depends(get_db)) -> HealthResponse:
    if not get_llm_enabled(db):
        llm = "disabled"
    else:
        llm = "ok" if settings.llm_configured else "not_configured"
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        db="ok",
        llm=llm,
    )
