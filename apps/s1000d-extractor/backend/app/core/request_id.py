"""Request ID middleware — generates uuid4, propagates via header + structlog contextvars."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-Id"
log = structlog.get_logger("s1000d_extractor.http")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        started = perf_counter()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response: Response | None = None
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        except Exception:
            if request.url.path.startswith("/api/"):
                log.exception(
                    "api_request_failed",
                    method=request.method,
                    path=request.url.path,
                    status_code=500,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                )
            raise
        finally:
            if request.url.path.startswith("/api/") and response is not None:
                log.info(
                    "api_request",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                )
            structlog.contextvars.clear_contextvars()
