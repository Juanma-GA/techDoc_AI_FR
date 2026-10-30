"""Persistence for the normal/demo application mode."""

from __future__ import annotations

from threading import RLock

from sqlalchemy.orm import Session

from app.db.models import AppConfig

DEMO_MODE_KEY = "demo_enabled"
_cached: bool | None = None
_cache_lock = RLock()


def reset_demo_cache() -> None:
    global _cached
    with _cache_lock:
        _cached = None


def current_demo_enabled() -> bool:
    """Process-local cache: the local launcher must use a single worker."""
    global _cached
    from app.db.session import SessionLocal

    with _cache_lock:
        if _cached is None:
            with SessionLocal() as db:
                _cached = get_demo_enabled(db)
        return _cached


def get_demo_enabled(db: Session) -> bool:
    row = db.get(AppConfig, DEMO_MODE_KEY)
    return row is not None and row.value.strip().lower() in {"1", "true", "yes"}


def is_demo_mode(db: Session) -> bool:
    return bool(db.info.get("demo_mode", False))


def set_demo_enabled(db: Session, enabled: bool) -> None:
    global _cached
    value = "true" if enabled else "false"
    row = db.get(AppConfig, DEMO_MODE_KEY)
    if row is None:
        db.add(AppConfig(key=DEMO_MODE_KEY, value=value))
    else:
        row.value = value
    with _cache_lock:
        db.commit()
        _cached = enabled
