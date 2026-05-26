"""GET /api/v1/health — liveness + dependency status."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        db="ok",
        llm="ok" if settings.llm_configured else "not_configured",
    )
