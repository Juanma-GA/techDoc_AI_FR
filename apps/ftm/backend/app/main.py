"""FastAPI app factory — `create_app()` returns a configured FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    admin, analysis, anomalies, chat, files, health, i18n, kpis, projects,
    settings as settings_api,
)
from app.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_id import REQUEST_ID_HEADER, RequestIdMiddleware


# Vite build output, served only when present (i.e. after `pnpm build`
# or when the repo has been packaged with `scripts/package.bat`).
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestIdMiddleware)

    register_error_handlers(app)

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(health.router)
    api_v1.include_router(projects.router)
    api_v1.include_router(files.router)
    api_v1.include_router(analysis.router)
    api_v1.include_router(anomalies.router)
    api_v1.include_router(kpis.router)
    api_v1.include_router(chat.router)
    api_v1.include_router(settings_api.router)
    api_v1.include_router(i18n.router)
    api_v1.include_router(admin.router)
    app.include_router(api_v1)

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the prebuilt SPA if the Vite bundle is present, otherwise
    fall back to the static preview page (token-driven, no Node required).

    API routes are registered first, so /api/v1/* never reaches either
    fallback. Real files (favicon, vite.svg…) are served from disk after
    a path-traversal guard; anything else hands back index.html.
    """
    if FRONTEND_DIST.is_dir():
        _mount_vite_dist(app)
    else:
        _mount_preview(app)


def _mount_vite_dist(app: FastAPI) -> None:
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    dist_resolved = FRONTEND_DIST.resolve()
    index_html = FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)

        candidate = (FRONTEND_DIST / full_path).resolve()
        try:
            candidate.relative_to(dist_resolved)
        except ValueError:
            raise HTTPException(status_code=404)

        if candidate.is_file():
            return FileResponse(candidate)
        if not index_html.exists():
            raise HTTPException(status_code=500, detail="frontend dist incomplete")
        return FileResponse(index_html)


def _mount_preview(app: FastAPI) -> None:
    """Static fallback used when no Vite dist exists (no Node available)."""
    from app.api.preview import render_preview

    @app.get("/", include_in_schema=False)
    def preview_root() -> HTMLResponse:
        return render_preview()


app = create_app()
