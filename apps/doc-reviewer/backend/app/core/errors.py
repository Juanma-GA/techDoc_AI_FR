"""Unified error handling — every error response shares the shape

    {code, message, detail, request_id}

See docs/adr/0003-error-format.md.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request


logger = structlog.get_logger(__name__)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        detail: Any = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.status_code = status_code


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _payload(code: str, message: str, detail: Any, request_id: str) -> dict[str, Any]:
    return {"code": code, "message": message, "detail": detail, "request_id": request_id}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _on_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("app_error", code=exc.code)
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.detail, _request_id(request)),
        )

    @app.exception_handler(HTTPException)
    async def _on_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        detail = None if isinstance(exc.detail, str) else exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(
                code=f"HTTP_{exc.status_code}",
                message=message,
                detail=detail,
                request_id=_request_id(request),
            ),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_payload(
                code="VALIDATION_ERROR",
                message="Données d'entrée invalides",
                detail=exc.errors(),
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(Exception)
    async def _on_unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=_payload(
                code="INTERNAL_ERROR",
                message="Erreur interne",
                detail=None,
                request_id=_request_id(request),
            ),
        )
