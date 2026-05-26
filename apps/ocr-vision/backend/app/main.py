"""FastAPI app factory - `create_app()` returns a configured FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, health, vision
from app.api import settings as settings_route
from app.api.preview import render_preview
from app.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_id import REQUEST_ID_HEADER, RequestIdMiddleware


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
    api_v1.include_router(settings_route.router)
    api_v1.include_router(admin.router)
    api_v1.include_router(vision.router)
    app.include_router(api_v1)

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Sert le SPA Vite si `frontend/dist/` existe, sinon retombe sur le
    preview HTML autonome (vanilla JS + design-tokens). Routes /api/v1/*
    sont enregistrees AVANT, donc elles ont priorite.
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
        except ValueError as exc:
            raise HTTPException(status_code=404) from exc

        if candidate.is_file():
            return FileResponse(candidate)
        if not index_html.exists():
            raise HTTPException(status_code=500, detail="frontend dist incomplete")
        return FileResponse(index_html)


def _mount_preview(app: FastAPI) -> None:
    """Fallback statique quand frontend/dist/ n'existe pas (Node absent)."""

    @app.get("/", include_in_schema=False)
    def preview_root() -> HTMLResponse:
        return render_preview()


app = create_app()
