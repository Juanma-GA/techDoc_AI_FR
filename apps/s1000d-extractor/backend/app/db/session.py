"""SQLAlchemy 2 engine + session + Base."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def _configured_demo_database_url() -> URL:
    normal_url = make_url(settings.database_url)
    if settings.demo_database_url:
        demo_url = make_url(settings.demo_database_url)
    elif normal_url.get_backend_name() == "sqlite" and normal_url.database:
        normal_path = Path(normal_url.database)
        if normal_path.name == ":memory:":
            raise RuntimeError(
                "DEMO_DATABASE_URL must be configured when DATABASE_URL uses SQLite memory storage."
            )
        demo_path = normal_path.with_name(f"{normal_path.stem}-demo{normal_path.suffix}")
        demo_url = normal_url.set(database=str(demo_path))
    else:
        raise RuntimeError(
            "DEMO_DATABASE_URL must be configured when DATABASE_URL is not a file-based SQLite database."
        )
    if demo_url.get_backend_name() == "sqlite":
        if not demo_url.database or demo_url.database == ":memory:":
            raise RuntimeError("DEMO_DATABASE_URL must use persistent SQLite file storage.")
        if normal_url.get_backend_name() == "sqlite" and normal_url.database:
            if Path(normal_url.database).resolve() == Path(demo_url.database).resolve():
                raise RuntimeError("DEMO_DATABASE_URL must not point to the normal database.")
    elif demo_url == normal_url:
        raise RuntimeError("DEMO_DATABASE_URL must not point to the normal database.")
    return demo_url


demo_database_url = _configured_demo_database_url()


def _ensure_data_dir(database_url: str | URL) -> None:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        db_path = Path(url.database)
        db_path.parent.mkdir(parents=True, exist_ok=True)


def _make_engine(database_url: str | URL):
    url = make_url(database_url)
    _ensure_data_dir(url)
    engine = create_engine(
        url,
        future=True,
        connect_args={"check_same_thread": False} if url.get_backend_name() == "sqlite" else {},
    )
    if url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_wal)
    return engine


def _enable_sqlite_wal(dbapi_connection, _) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = _make_engine(settings.database_url)
demo_engine = _make_engine(demo_database_url)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
DemoSessionLocal = sessionmaker(bind=demo_engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def open_session(demo_mode: bool = False) -> Session:
    db = (DemoSessionLocal if demo_mode else SessionLocal)()
    db.info["demo_mode"] = demo_mode
    return db


def storage_directory(db: Session) -> Path:
    if not db.info.get("demo_mode", False):
        return Path(settings.storage_dir)
    if settings.demo_storage_dir:
        demo_directory = Path(settings.demo_storage_dir)
    else:
        normal_directory = Path(settings.storage_dir)
        demo_directory = normal_directory.with_name(f"{normal_directory.name}-demo")
    if demo_directory.resolve() == Path(settings.storage_dir).resolve():
        raise RuntimeError("DEMO_STORAGE_DIR must not point to the normal storage directory.")
    return demo_directory


def get_db() -> Generator[Session, None, None]:
    control_db = SessionLocal()
    from app.core.demo_mode import get_demo_enabled

    demo_mode = get_demo_enabled(control_db)
    if demo_mode:
        control_db.close()
        db = open_session(demo_mode=True)
    else:
        db = control_db
        db.info["demo_mode"] = False
    try:
        yield db
    finally:
        db.close()


def get_control_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    db.info["demo_mode"] = False
    try:
        yield db
    finally:
        db.close()
