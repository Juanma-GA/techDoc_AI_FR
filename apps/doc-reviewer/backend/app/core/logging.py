"""structlog JSON configuration — single entry point: configure_logging()."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from typing import Any

import structlog


def parse_log_level(value: str | None) -> int:
    normalized = (value or "INFO").strip().upper()
    if normalized in {"NONE", "OFF", "DISABLED"}:
        return logging.CRITICAL + 1
    return getattr(logging, normalized, logging.INFO)


def sanitize_llm_debug(value: Any, *, _key: str = "") -> Any:
    key = _key.lower()
    if key in {"authorization", "api_key", "apikey", "token", "password", "secret"}:
        return "<redacted>"
    if isinstance(value, bytes):
        return {"bytes": len(value)}
    if isinstance(value, Mapping):
        return {
            str(item_key): sanitize_llm_debug(item_value, _key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_llm_debug(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_llm_debug(item) for item in value]
    if isinstance(value, str):
        match = re.fullmatch(r"data:([^;]+);base64,(.*)", value, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return {"inline_image": match.group(1), "base64_chars": len(match.group(2))}
        return {"text_chars": len(value)}
    return value


def configure_logging(level: str = "INFO") -> None:
    log_level = parse_log_level(level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(min(log_level, logging.CRITICAL)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)
    for noisy in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        noisy_logger = logging.getLogger(noisy)
        noisy_logger.propagate = True
        if noisy == "uvicorn.access":
            noisy_logger.disabled = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
