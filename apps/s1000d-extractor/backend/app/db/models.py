"""SQLAlchemy 2.0 models pour s1000d-extractor.

- `AppConfig`    : key/value runtime (cle Mistral). Preserve par les resets.
- `BrexProfile`  : un BREX projet reutilisable (uploade une fois, applique a
  tous les documents du projet -> evite le remapping par document).
- `Document`     : un document source (PDF/DOCX) et le resultat de sa migration
  (arbre IR + XML S1000D + violations).

Types choisis SQLite ET Postgres-compatibles (String/Text/DateTime/Integer).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")


class BrexProfile(Base):
    __tablename__ = "brex_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    s1000d_issue: Mapped[str] = mapped_column(String(10))
    xml_path: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(500))
    source_format: Mapped[str] = mapped_column(String(10))          # "pdf" | "docx"
    s1000d_issue: Mapped[str] = mapped_column(String(10), default="5.0")
    context_hint: Mapped[str] = mapped_column(String(20), default="mixed")
    brex_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("brex_profiles.id", ondelete="SET NULL"), nullable=True
    )
    storage_path: Mapped[str] = mapped_column(String(1000))
    xml_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="uploaded", index=True)
    dm_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ir_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    violations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Wizard (configuration etape par etape) :
    wizard_step: Mapped[str | None] = mapped_column(String(20), nullable=True)
    split_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dms_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
