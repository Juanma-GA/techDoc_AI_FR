"""Persisted comparisons, isolated from the document-review library."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DocumentComparison(Base):
    __tablename__ = "document_comparisons"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_index: Mapped[int] = mapped_column(Integer, nullable=False)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    ai_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_status: Mapped[str] = mapped_column(
        String(30), default="pending", server_default="pending", nullable=False
    )
    ai_summary_truncated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
