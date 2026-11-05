"""GET /api/v1/health — liveness + dependency probes (db, llm)."""

from __future__ import annotations

import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
import structlog
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.core.demo_mode import visible_projects
from app.core.mistral_client import (
    get_effective_settings,
    get_llm_enabled,
    get_llm_tested,
    set_llm_tested,
)
from app.db.models import File, FileVersion
from app.db.session import get_db

router = APIRouter(tags=["health"])
logger = structlog.get_logger(__name__)


class SourceProbe(BaseModel):
    configured: int
    available: int
    unavailable: int


class ConnectivityOut(BaseModel):
    checked_at: datetime
    sources: dict[str, SourceProbe]
    ai_enabled: bool
    ai_connection: Literal["disabled", "not_configured", "connected", "rejected", "unreachable"]


def _probe_paths(paths: list[str | None], *, directory: bool = False) -> SourceProbe:
    available = 0
    for path in paths:
        if not path:
            continue
        try:
            mode = Path(path).stat().st_mode
            expected_type = stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)
            if expected_type and os.access(path, os.R_OK | (os.X_OK if directory else 0)):
                available += 1
            else:
                logger.warning("connectivity_source_inaccessible", directory=directory)
        except OSError as exc:
            logger.warning("connectivity_source_probe_failed", error=type(exc).__name__)
    return SourceProbe(configured=len(paths), available=available, unavailable=len(paths) - available)


@router.get("/health/connectivity", response_model=ConnectivityOut)
async def connectivity(response: Response, db: Session = Depends(get_db)) -> ConnectivityOut:
    """Probe source metadata and provider reachability without reading documents."""
    response.headers["Cache-Control"] = "no-store"
    projects = visible_projects(db)
    latest_path = (
        select(FileVersion.storage_path)
        .where(FileVersion.file_id == File.id)
        .order_by(FileVersion.uploaded_at.desc(), FileVersion.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    paths = list(
        db.scalars(
            select(latest_path)
            .select_from(File)
            .where(
                File.project_id.in_([project.id for project in projects]),
            )
        )
    )
    sources = {
        "documents": await run_in_threadpool(_probe_paths, paths),
        "folder": await run_in_threadpool(
            _probe_paths, [p.corpus_path for p in projects if p.corpus_path], directory=True
        ),
        "reference": await run_in_threadpool(
            _probe_paths, [p.reference_path for p in projects if p.reference_path]
        ),
        "basl": await run_in_threadpool(_probe_paths, [p.basl_path for p in projects if p.basl_path]),
    }
    enabled = get_llm_enabled(db)
    connection: Literal["disabled", "not_configured", "connected", "rejected", "unreachable"]
    connection = "disabled" if not enabled else "not_configured"
    if enabled:
        effective = get_effective_settings(db)
        if effective["api_key"]:
            try:
                async with httpx.AsyncClient(timeout=3.0, follow_redirects=False) as client:
                    provider_response = await client.get(
                        f"{effective['base_url'].rstrip('/')}/v1/models",
                        headers={"Authorization": f"Bearer {effective['api_key']}"},
                    )
                connection = "connected" if provider_response.is_success else "rejected"
                if connection == "rejected":
                    logger.warning("connectivity_provider_rejected", status=provider_response.status_code)
            except httpx.RequestError as exc:
                connection = "unreachable"
                logger.warning("connectivity_provider_unreachable", error=type(exc).__name__)
            if connection in {"rejected", "unreachable"} and get_llm_tested(db):
                set_llm_tested(db, False)
    return ConnectivityOut(
        checked_at=datetime.now(UTC),
        sources=sources,
        ai_enabled=enabled,
        ai_connection=connection,
    )


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
