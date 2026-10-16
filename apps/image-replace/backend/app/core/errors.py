"""Unified error format `{code, message, detail, request_id}` for all non-2xx responses."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_id import REQUEST_ID_HEADER


class AppError(Exception):
    """Domain error with stable code, raised in business code."""

    def __init__(self, code: str, message: str, status_code: int = 400, detail: Any = None) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


def _payload(code: str, message: str, detail: Any, request_id: str) -> dict[str, Any]:
    return {"code": code, "message": message, "detail": detail, "request_id": request_id}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        rid = request.headers.get(REQUEST_ID_HEADER, "")
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.detail, rid),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = request.headers.get(REQUEST_ID_HEADER, "")
        return JSONResponse(
            status_code=422,
            content=_payload("VALIDATION_ERROR", "Invalid request", [
                {"type": error["type"], "loc": error["loc"], "msg": error["msg"]}
                for error in exc.errors()
            ], rid),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        rid = request.headers.get(REQUEST_ID_HEADER, "")
        code = "HTTP_ERROR" if not isinstance(exc, HTTPException) else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(code, str(exc.detail), None, rid),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = request.headers.get(REQUEST_ID_HEADER, "")
        return JSONResponse(
            status_code=500,
            content=_payload("INTERNAL_ERROR", "Unexpected server error", None, rid),
        )
