"""FastAPI app factory — `create_app()` returns a configured FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, analyze, documents, health, rules, standards
from app.api import settings as settings_api
from app.api import suggestions
from app.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_id import REQUEST_ID_HEADER, RequestIdMiddleware
from app.db.seed import seed_default_rules
from app.db.session import SessionLocal


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
    api_v1.include_router(documents.router)
    api_v1.include_router(analyze.router)
    api_v1.include_router(suggestions.router)
    api_v1.include_router(rules.router)
    api_v1.include_router(standards.router)
    api_v1.include_router(settings_api.router)
    api_v1.include_router(admin.router)
    app.include_router(api_v1)

    _seed_defaults()
    _mount_frontend(app)

    return app


def _seed_defaults() -> None:
    """Insert demo custom rules at boot if the table is empty (idempotent)."""
    db = SessionLocal()
    try:
        seed_default_rules(db)
    except Exception:  # noqa: BLE001 — seed must never block startup
        pass
    finally:
        db.close()


def _mount_frontend(app: FastAPI) -> None:
    """Sert l'app React buildee (`frontend/dist/`). React est obligatoire (plus
    de preview HTML). Si le dist est absent, `/` renvoie un message 503 « build
    requis ». Les routes `/api/v1/*` sont enregistrees AVANT, donc prioritaires.
    """
    if not FRONTEND_DIST.is_dir():
        _mount_missing_dist(app)
        return

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
        except ValueError as exc:
            raise HTTPException(status_code=404) from exc

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
