"""GET /api/v1/health — liveness + dependency status."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.core.mistral_client import get_effective_settings, get_llm_enabled, get_llm_tested
from app.db.session import get_db
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(db: Session = Depends(get_db)) -> HealthResponse:
    # Vert (ON) seulement si: cle effective (DB ou .env) presente + dernier test
    # reussi + LLM active. Sinon: disabled / not_configured / untested.
    if not get_llm_enabled(db):
        llm = "disabled"
    elif not get_effective_settings(db)["api_key"]:
        llm = "not_configured"
    elif not get_llm_tested(db):
        llm = "untested"
    else:
        llm = "ok"
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        db="ok",
        llm=llm,
    )
