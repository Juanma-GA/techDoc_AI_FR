from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DocumentPreparation(Base):
    __tablename__ = "document_preparations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    source_filename: Mapped[str] = mapped_column("reference_filename", String(500), nullable=False)
    source_sha256: Mapped[str] = mapped_column("reference_sha256", String(64), nullable=False)
    page_count: Mapped[int] = mapped_column("reference_page_count", Integer, nullable=False)
    source_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_metadata_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    ocr_results_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    validated_pages_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    selected_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    page_decisions_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    preparation_mapping_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    page_classification_json: Mapped[str] = mapped_column(
        Text, default="{}", server_default="{}"
    )
    absent_page_types_json: Mapped[str] = mapped_column(
        Text, default="[]", server_default="[]"
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class PreparationChecklist(Base):
    __tablename__ = "preparation_checklists"

    client_code: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    rules_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
