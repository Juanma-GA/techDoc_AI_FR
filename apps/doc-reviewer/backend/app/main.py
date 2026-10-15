"""FastAPI app factory — `create_app()` returns a configured FastAPI."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException

# Windows n'enregistre pas `.mjs` dans son registre MIME : StaticFiles le sert
# alors en application/octet-stream, et le navigateur REFUSE de charger un
# worker ES-module avec ce type -> "failed to load pdf" (react-pdf charge
# `pdf.worker.min.mjs` comme worker module). On force le bon type ici, au
# niveau processus, avant tout mount StaticFiles. Idempotent.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect

from app.api import admin, analyze, documents, health, rules, standards, suggestions
from app.api import settings as settings_api
from app.checks.client_registry import (
    LoadedClientConfiguration,
    active_standard_versions,
    load_active_client_configuration,
)
from app.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_guard import CSRF_HEADER, RequestGuardMiddleware
from app.core.request_id import REQUEST_ID_HEADER, RequestIdMiddleware
from app.db.seed import sync_user_standard
from app.db.session import SessionLocal

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


def _is_exposed_deployment() -> bool:
    """Deploiement expose = bind non local, OU instance declaree derriere un
    reverse proxy (BEHIND_AUTH_PROXY) meme si uvicorn reste sur 127.0.0.1 —
    cas d'un nginx place devant l'application dans le meme hote/conteneur."""
    return not _is_local_bind() or settings.behind_auth_proxy


def _validate_encryption_key() -> None:
    """Une ENCRYPTION_KEY fournie mais invalide est refusee dans TOUS les modes :
    sinon la cle Mistral stockee devenait silencieusement indechiffrable (lue
    comme « absente ») au lieu d'echouer clairement."""
    if not settings.encryption_key:
        return
    from app.core.encryption import EncryptionError, SecretManager

    try:
        SecretManager(settings.encryption_key)
    except EncryptionError as exc:
        raise RuntimeError(
            "ENCRYPTION_KEY invalide (cle Fernet attendue : 32 octets en base64 "
            "url-safe, 44 caracteres). Generer une cle via "
            "app.core.encryption.generate_key()."
        ) from exc


def _validate_security_posture() -> None:
    """Refuse de demarrer en posture deploiement (bind expose ou reverse proxy)
    si les protections sensibles ne sont pas configurees. Inerte en local
    (bind 127.0.0.1 sans proxy) ; l'exposition non declaree est en plus
    bloquee requete par requete par `core.request_guard`."""
    _validate_encryption_key()
    if not _is_exposed_deployment():
        return

    problems: list[str] = []
    if not settings.behind_auth_proxy:
        problems.append(
            "BEHIND_AUTH_PROXY non atteste : l'application n'a aucune "
            "authentification integree et ne doit etre exposee que derriere un "
            "reverse proxy authentifiant (SSO). Mettre BEHIND_AUTH_PROXY=true "
            "uniquement si c'est le cas."
        )
    if not settings.encryption_configured:
        problems.append(
            "ENCRYPTION_KEY manquante ou trop courte : la sauvegarde des cles Mistral est "
            "refusee. Generer une cle via app.core.encryption.generate_key()."
        )
    leftover = [o for o in settings.cors_origins if _is_local_origin(o)]
    if leftover:
        problems.append(
            "CORS_ORIGINS contient des origines locales de dev "
            f"({', '.join(leftover)}). Definir uniquement les origines de prod."
        )
    if problems:
        raise RuntimeError(
            "Posture de securite invalide pour un deploiement expose ("
            f"BIND_HOST={settings.bind_host}, BEHIND_AUTH_PROXY="
            f"{settings.behind_auth_proxy}) :\n  - " + "\n  - ".join(problems)
        )


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    _validate_security_posture()
    client_configuration = load_active_client_configuration()
    demo_client_configuration = load_active_client_configuration(
        environ={"CLIENT_BUNDLE": "demo_rules"}
    )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )
    app.state.client_configuration = client_configuration
    app.state.demo_client_configuration = demo_client_configuration

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", CSRF_HEADER, REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestIdMiddleware)
    # Ajoute en DERNIER = middleware le plus externe : Host / Origin / en-tete
    # anti-CSRF / exposition sont verifies avant tout traitement (CORS compris).
    app.add_middleware(RequestGuardMiddleware)

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

    _sync_standard_catalogs(client_configuration, demo_client_configuration)
    _mount_frontend(app)

    return app


def _sync_standard_catalogs(
    *client_configurations: LoadedClientConfiguration,
) -> None:
    """Synchronize the editable catalogs for normal and demo modes."""
    db = SessionLocal()
    try:
        # Pytest imports the application before its fixture creates the schema.
        # In a migrated installation the table exists and sync errors are fatal.
        if not inspect(db.get_bind()).has_table("standards"):
            return
        for client_configuration in client_configurations:
            sync_user_standard(db, client_configuration.bundle.standard_specs)
            active_standard_versions(db, client_configuration)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Client standard catalog synchronization failed") from exc
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

        relative = _safe_dist_relative_path(full_path)
        if relative is None:
            raise HTTPException(status_code=404)
        candidate = FRONTEND_DIST.joinpath(*relative).resolve()
        try:
            candidate.relative_to(dist_resolved)
        except ValueError as exc:
            raise HTTPException(status_code=404) from exc

        if candidate.is_file() and candidate.name != "index.html":
            return FileResponse(candidate)
        if not index_html.exists():
            raise HTTPException(status_code=500, detail="frontend dist incomplete")
        return FileResponse(index_html, headers=no_cache)


def _safe_dist_relative_path(full_path: str) -> tuple[str, ...] | None:
    """Valide LEXICALEMENT un chemin d'URL avant tout acces disque.

    Le controle `relative_to` apres `resolve()` arrivait trop tard sous Windows :
    `/%5C%5Chote%5Cpartage` donne `\\\\hote\\partage`, un chemin UNC que
    `resolve()` / `is_file()` ouvrent -> connexion SMB sortante et fuite du hash
    NTLM de l'utilisateur, declenchable par une simple balise <img> d'un site
    tiers. On refuse donc separateurs Windows, lecteurs, flux NTFS (`:`),
    octets nuls, chemins absolus et segments `..` sans toucher au disque.
    """
    if not full_path:
        return ()
    if any(ch in full_path for ch in ("\\", ":", "\x00")):
        return None
    if full_path.startswith("/"):
        return None
    parts = tuple(part for part in full_path.split("/") if part not in ("", "."))
    if any(part == ".." for part in parts):
        return None
    return parts


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
