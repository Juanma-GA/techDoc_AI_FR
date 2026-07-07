"""SQLAlchemy 2.0 models pour le POC Cati.

- `AppConfig` (key/value) : config runtime standard (cle Mistral, interrupteurs).
- `CatiDocument` : un PDF plan de montage uploade + metadonnees d'extraction.
- `CatiItem` : une ligne de nomenclature extraite (editable), rattachee a un doc.

Types compatibles SQLite ET Postgres : UUID stocke en `String(36)`, JSON metier
serialise en `Text` (pas de type JSON SQLite-specifique).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")


class CatiDocument(Base):
    __tablename__ = "cati_document"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(120), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    storage_path: Mapped[str] = mapped_column(String(1000), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)

    # pending | extracted | error
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # deterministic | llm | mixed
    extraction_method: Mapped[str] = mapped_column(String(16), default="deterministic")

    header_meta: Mapped[str] = mapped_column(Text, default="{}")     # JSON (metadonnees document saisies)
    extraction_meta: Mapped[str] = mapped_column(Text, default="{}")  # JSON (colonnes detectees, warnings)
    challenge: Mapped[str] = mapped_column(Text, default="{}")        # JSON (rapport de controle LLM)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    items: Mapped[list["CatiItem"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="CatiItem.order_index",
    )


class CatiItem(Base):
    __tablename__ = "cati_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cati_document.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # JSON : champs logiques mappes (fig, figreflink, aplomb, description,
    # matiere, ref_interne, ref_client, ref_fournisseur, qty, symbole).
    fields: Mapped[str] = mapped_column(Text, default="{}")

    included: Mapped[bool] = mapped_column(Boolean, default=True)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped["CatiDocument"] = relationship(back_populates="items")
