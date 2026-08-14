"""FastAPI app factory - `create_app()` returns a configured FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, brex, extract, health, resources, wizard
from app.api import settings as settings_route
from app.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_id import REQUEST_ID_HEADER, RequestIdMiddleware

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


# Hotes consideres « locaux » (palier 1, regle #8). Tant que le bind reste l'un
# d'eux, la posture local-first s'applique : chiffrement et origines CORS prod
# restent optionnels. Des que l'IT bascule sur un bind expose (deploiement
# palier 2/3 via .env), les protections deviennent OBLIGATOIRES (fail-fast).
_LOCAL_BIND_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _is_local_bind() -> bool:
    return settings.bind_host.strip().lower() in _LOCAL_BIND_HOSTS


def _is_local_origin(origin: str) -> bool:
    o = origin.lower()
    return "localhost" in o or "127.0.0.1" in o or "[::1]" in o


def _validate_security_posture() -> None:
    """Refuse de demarrer en posture deploiement (bind expose) si les protections
    sensibles ne sont pas configurees. Inerte en local (bind 127.0.0.1)."""
    if _is_local_bind():
        return

    problems: list[str] = []
    if not settings.encryption_configured:
        problems.append(
            "ENCRYPTION_KEY manquante ou trop courte : la cle Mistral serait "
            "stockee en clair. Generer une cle via app.core.encryption.generate_key()."
        )
    leftover = [o for o in settings.cors_origins if _is_local_origin(o)]
    if leftover:
        problems.append(
            "CORS_ORIGINS contient des origines locales de dev "
            f"({', '.join(leftover)}). Definir uniquement les origines de prod."
        )
    if problems:
        raise RuntimeError(
            "Posture de securite invalide pour un bind expose ("
            f"BIND_HOST={settings.bind_host}) :\n  - " + "\n  - ".join(problems)
        )


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    _validate_security_posture()

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
    api_v1.include_router(brex.router)
    api_v1.include_router(extract.router)
    api_v1.include_router(resources.router)
    api_v1.include_router(wizard.router)
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
