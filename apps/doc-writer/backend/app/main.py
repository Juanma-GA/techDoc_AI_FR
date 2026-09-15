"""FastAPI app factory — `create_app()` returns a configured FastAPI.

**Tier Modes (AACF HR8 — Configuration)**

- **Tier 1 (local-only)** : development, bind 127.0.0.1, no auth required (default,
  the ONLY tier supported by the monorepo standard — CLAUDE.md rule #8 /
  STANDARD_POC.md §3.5: "Tout POC est local seul"). Set `TIER_MODE=tier1` in
  `.env`. Encryption and strict CORS are optional.

- **Tier 2 (cloud / exposed bind)** : out of the POC standard's scope. An
  MFA pilot (R1, `settings.auth_enabled`) now exists: `_validate_security_posture()`
  allows a non-local bind **only if** `settings.auth_fully_configured` is
  true (AUTHDB + MS365 identity endpoint + CA bundle all wired) — otherwise
  it still refuses to start (fail-fast `RuntimeError`), exactly as before the
  pilot. See `README.md` (`## Auth`) and
  `MFA_PILOT_CHECKLIST_DOC-WRITER_2026-09-14.md` for the documented écart and
  scope.

The tier mode is validated at startup via `_validate_security_posture()`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, documents, export, health, sessions
from app.api import auth as auth_route
from app.api import settings as settings_route
from app.config import settings
from app.core.auth_middleware import AuthMiddleware
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
    # `exposed_behind_proxy` : uvicorn ecoute bien sur 127.0.0.1, mais un
    # reverse-proxy rend l'app joignable de l'exterieur -> traiter comme
    # NON-local pour la posture de securite (sinon F-02 laisserait passer un
    # deploiement expose sans auth). Le flag doit donc "gagner" sur le bind.
    if settings.exposed_behind_proxy:
        return False
    return settings.bind_host.strip().lower() in _LOCAL_BIND_HOSTS


def _is_local_origin(origin: str) -> bool:
    o = origin.lower()
    return "localhost" in o or "127.0.0.1" in o or "[::1]" in o


def _validate_security_posture() -> None:
    """Refuse de demarrer en posture deploiement (bind expose) si les protections
    sensibles ne sont pas configurees. Inerte en local (bind 127.0.0.1).

    F-02 (hardening 2026-09-14) : palier 2/3 est hors perimetre du standard POC
    (CLAUDE.md regle #8 / STANDARD_POC.md §3.5). A l'origine, AUCUN middleware
    d'auth n'existait dans cette app et tout bind non-local etait bloque
    inconditionnellement.

    MFA pilot (R1, 2026-09-14, cf. MFA_PILOT_CHECKLIST_DOC-WRITER_2026-09-14.md) :
    un middleware d'auth deleguee (service MCP d'identite MS365 + AUTHDB
    Postgres dediee) existe desormais. Un bind non-local n'est autorise QUE si
    `settings.auth_fully_configured` est vrai (AUTHDB + endpoint MS365 + CA
    bundle si https, TOUS configures) ; sinon le comportement reste
    IDENTIQUE a avant ce pilote : blocage inconditionnel, fail-fast.
    """
    # Tier1 (local) : skip security checks.
    if settings.tier_mode.lower() == "tier1" and _is_local_bind():
        return

    # Tier2 (cloud) ou bind expose : validation stricte.
    problems: list[str] = []

    # Auth reelle presente uniquement si TOUT le bloc MFA pilot est configure
    # (settings.auth_fully_configured) ; sinon, meme blocage qu'avant ce pilote.
    if not settings.auth_fully_configured:
        problems.append(
            "Aucune authentification pleinement configuree pour cette app "
            "(palier 2/3 hors perimetre du standard POC, CLAUDE.md regle #8). "
            "TIER_MODE=tier2 / un bind non-local ne peuvent pas demarrer tant "
            "que auth_enabled + AUTHDB + ms365_mcp_endpoint (+ ms365_ca_bundle "
            "si https) ne sont pas TOUS configures. Voir README.md ## Auth et "
            "MFA_PILOT_CHECKLIST_DOC-WRITER_2026-09-14.md."
        )

    # Tier2 specific : auth/encryption/CORS strictes sont OBLIGATOIRES.
    if settings.tier_mode.lower() == "tier2":
        if not settings.encryption_configured:
            problems.append(
                "TIER_MODE=tier2 (cloud) : ENCRYPTION_KEY manquante ou trop courte. "
                "Generer une cle via app.core.encryption.generate_key() et la passer via .env."
            )
        leftover = [o for o in settings.cors_origins if _is_local_origin(o)]
        if leftover:
            problems.append(
                "TIER_MODE=tier2 (cloud) : CORS_ORIGINS contient des origines de dev "
                f"({', '.join(leftover)}). Definir uniquement les origines de prod."
            )
    
    # Bind expose (hote non-local) : securite obligatoire independemment du tier.
    elif not _is_local_bind():
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
            "Posture de securite invalide (TIER_MODE="
            f"{settings.tier_mode}, BIND_HOST={settings.bind_host}) :\n  - "
            + "\n  - ".join(problems)
        )


logger = logging.getLogger("doc_writer.main")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """MFA pilot (R1) : initialise l'AUTHDB Postgres dediee au demarrage,
    fail-closed (une erreur ici interrompt le demarrage, jamais de repli
    "continue sans auth") — inerte tant que `auth_enabled=False`."""
    if settings.auth_enabled:
        from app.core.auth_db import get_auth_db_service

        get_auth_db_service().initialize()
        logger.info("MFA pilot: AUTHDB initialized")
    yield


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
        lifespan=_lifespan,
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
    # MFA pilot (R1) : peuple request.state.user sur chaque requete HTTP ;
    # no-op tant que auth_enabled=False (cf. app.core.auth_middleware).
    app.add_middleware(AuthMiddleware)

    register_error_handlers(app)

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(health.router)
    api_v1.include_router(documents.router)
    api_v1.include_router(sessions.router)
    api_v1.include_router(settings_route.router)
    api_v1.include_router(admin.router)
    api_v1.include_router(export.router)
    api_v1.include_router(auth_route.router)
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

    # index.html ne doit JAMAIS etre mis en cache par le navigateur : sinon,
    # apres un rebuild, il continue de pointer vers d'anciens assets hashes
    # (et l'UI ne se met pas a jour). Les assets sous /assets sont hashes donc
    # cacheables sans risque.
    _NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate"}

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
        return FileResponse(index_html, headers=_NO_CACHE)


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
