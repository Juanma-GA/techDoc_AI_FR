"""SQLAlchemy 2 engine + session + Base."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings


def _ensure_data_dir() -> None:
    if settings.database_url.startswith("sqlite:///"):
        target = settings.database_url.removeprefix("sqlite:///")
        if target == ":memory:":
            return
        db_path = Path(target)
        db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_data_dir()

# SQLite en memoire (tests) : une seule connexion partagee (StaticPool), sinon
# chaque thread ouvre sa propre base vide et perd le schema. Inerte en prod
# (base fichier), ou le pool par defaut convient.
_is_memory = ":memory:" in settings.database_url

engine = create_engine(
    settings.database_url,
    future=True,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    poolclass=StaticPool if _is_memory else None,
)


@event.listens_for(engine, "connect")
def _enable_sqlite_wal(dbapi_connection, _) -> None:  # type: ignore[no-untyped-def]
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
