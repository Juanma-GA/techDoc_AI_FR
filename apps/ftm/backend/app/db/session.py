"""SQLAlchemy 2 — `engine`, `SessionLocal`, `Base`, `get_db()`."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Single declarative base for the app — Alembic targets `Base.metadata`."""


def _ensure_sqlite_dir(url: str) -> None:
    """sqlite:///path/to/file.db — create parent dir if missing."""
    if not url.startswith("sqlite"):
        return
    # sqlite:///relative or sqlite:////absolute
    raw_path = url.split("///", 1)[-1]
    if not raw_path or raw_path == ":memory:":
        return
    Path(raw_path).resolve().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)
os.makedirs(settings.storage_dir, exist_ok=True)


_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    future=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    class_=Session,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
