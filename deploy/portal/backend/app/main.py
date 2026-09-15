"""FastAPI app factory for the atexispocs portal auth backend (SSO option A).

Serves the MFA login API (`/api/auth/*`). The portal's static launcher is
served by nginx (alias) in the deployed env; behind nginx this backend sits at
`/atexispocs/api/`. A `/api/health` endpoint mirrors the other apps' health
probe used by start-all.sh.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth as auth_route
from app.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.debug)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": settings.app_version}

    app.include_router(api)
    app.include_router(auth_route.router)
    return app


app = create_app()
