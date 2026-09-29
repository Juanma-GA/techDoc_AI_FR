"""Pytest configuration — runs before any test imports `app.*`.

Forces a temp-file SQLite (not :memory:, because each new connection to
`:memory:` opens an isolated DB) and a temp storage dir so tests never
touch the real `data/` folder.
"""

from __future__ import annotations

import os
import tempfile

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_db.name}")
os.environ.setdefault("STORAGE_DIR", tempfile.mkdtemp(prefix="doc-reviewer-tests-"))
os.environ.setdefault("LOG_LEVEL", "WARNING")


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.db.session import Base, engine  # noqa: E402
from app.db.models import AppConfig  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> None:
    Base.metadata.create_all(bind=engine)
    _seed_builtin_standards()


def _seed_builtin_standards() -> None:
    """Mirror the Alembic seed for tests (which bootstrap via `create_all`
    rather than `alembic upgrade`)."""
    import json

    from app.checks.standards import BUILTIN_STANDARDS, serialize_builtin_version
    from app.db.models import Standard, StandardVersion
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        if session.query(Standard).first() is not None:
            return
        for spec in BUILTIN_STANDARDS:
            std = Standard(
                code=spec["code"],
                label=spec["label"],
                description=spec.get("description"),
                builtin=True,
            )
            session.add(std)
            session.flush()
            for label in spec["versions"]:
                session.add(
                    StandardVersion(
                        standard_id=std.id,
                        label=label,
                        builtin=True,
                        catalog_json=json.dumps(serialize_builtin_version(spec, label)),
                    )
                )
        session.commit()
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def _reset_document_context_defaults() -> None:
    """Do not leak the persisted next-upload mapping between tests."""
    session = SessionLocal()
    try:
        session.execute(delete(AppConfig).where(AppConfig.key == "document.context_defaults"))
        session.commit()
    finally:
        session.close()


def _make_simple_pdf(text: str = "Torque value 12 cm and 5 in") -> bytes:
    """Build a minimal one-page PDF on the fly via PyMuPDF."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 100), text, fontname="helv", fontsize=12)
    raw = doc.tobytes()
    doc.close()
    return raw


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    return _make_simple_pdf()
