"""SQLAlchemy 2.0 models pour BRDP Manager.

- `AppConfig`     — config runtime generique (cle Mistral, cf. template).
- `ProjectConfig` — metadonnees du projet S1000D (ligne unique, id=1).
- `Brdp`          — un enregistrement BRDP (Business Rules Decision Point).
- `Note`          — note persistante attachee a un BRDP (1-1).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")


class ProjectConfig(Base):
    """Ligne unique (id=1) — metadonnees S1000D du projet."""

    __tablename__ = "project_config"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    project_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    model_ident_code: Mapped[str] = mapped_column(String(20), default="", server_default="")
    system_diff_code: Mapped[str] = mapped_column(String(4), default="A", server_default="A")
    issue_number: Mapped[str] = mapped_column(String(10), default="001", server_default="001")
    in_work: Mapped[str] = mapped_column(String(10), default="00", server_default="00")
    language_iso: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    country_iso: Mapped[str] = mapped_column(String(10), default="US", server_default="US")
    security_classification: Mapped[str] = mapped_column(
        String(10), default="01", server_default="01"
    )
    enterprise_code: Mapped[str] = mapped_column(String(20), default="", server_default="")


class Brdp(Base):
    __tablename__ = "brdps"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", server_default="")
    definition: Mapped[str] = mapped_column(Text, default="", server_default="")
    proposal: Mapped[str] = mapped_column(Text, default="", server_default="")
    validation: Mapped[str] = mapped_column(String(20), default="Pending", server_default="Pending")
    comments: Mapped[str] = mapped_column(Text, default="", server_default="")
    history: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )


class Note(Base):
    __tablename__ = "notes"

    brdp_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("brdps.id", ondelete="CASCADE"), primary_key=True
    )
    text: Mapped[str] = mapped_column(Text, default="", server_default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )
