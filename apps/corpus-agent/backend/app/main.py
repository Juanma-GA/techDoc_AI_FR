"""FastAPI app factory — `create_app()` returns a configured FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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

# Rate limiter (slowapi). Actif par defaut ; les routes peuvent surcharger via
# le decorateur @limiter.limit(...). Voir settings.rate_limit_*.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default] if settings.rate_limit_enabled else [],
    enabled=settings.rate_limit_enabled,
)


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

    if settings.rate_limit_enabled:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    """Sert l'app React buildee (`frontend/dist/`). React est obligatoire (plus
    de preview HTML). Si le dist est absent, `/` renvoie un message 503 « build
    requis ». Les routes `/api/v1/*` sont enregistrees AVANT, donc prioritaires.
    """
    if FRONTEND_DIST.is_dir():
        _mount_vite_dist(app)
    else:
        _mount_missing_dist(app)


def _mount_vite_dist(app: FastAPI) -> None:
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    dist_resolved = FRONTEND_DIST.resolve()
    index_html = FRONTEND_DIST / "index.html"
    # index.html en no-cache : apres un rebuild il pointe vers de nouveaux assets
    # hashes. Les assets sous /assets sont hashes donc cacheables.
    no_cache = {"Cache-Control": "no-store, no-cache, must-revalidate"}

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)

        candidate = (FRONTEND_DIST / full_path).resolve()
        try:
            candidate.relative_to(dist_resolved)
        except ValueError:
            raise HTTPException(status_code=404)

        if candidate.is_file() and candidate.name != "index.html":
            return FileResponse(candidate)
        if not index_html.exists():
            raise HTTPException(status_code=500, detail="frontend dist incomplete")
        return FileResponse(index_html, headers=no_cache)


def _mount_missing_dist(app: FastAPI) -> None:
    """Pas de `frontend/dist/` : plus de preview de repli. Message clair invitant
    a builder le front (React obligatoire)."""

    @app.get("/", include_in_schema=False)
    def _missing() -> HTMLResponse:
        return HTMLResponse(
            "<!doctype html><meta charset='utf-8'>"
            "<body style='font-family:sans-serif;padding:40px;max-width:640px'>"
            "<h1>Frontend non builde</h1>"
            "<p>L'UI React n'est pas buildee. Lance <code>vite build</code> "
            "(ou <code>pnpm build</code>) dans <code>frontend/</code> puis relance "
            "le backend.</p>"
            "<p>API disponible sur <a href='/api/v1/docs'>/api/v1/docs</a>.</p>"
            "</body>",
            status_code=503,
        )


app = create_app()
