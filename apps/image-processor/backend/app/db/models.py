"""Local configuration, startup workbook, and complete image workspaces."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")


class ExcelPreset(Base):
    __tablename__ = "excel_preset"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    state: Mapped[str] = mapped_column(Text)


class ImageHistory(Base):
    __tablename__ = "image_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    piece_name: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    version: Mapped[int] = mapped_column(default=1)
    operation_count: Mapped[int] = mapped_column(default=0)
    state: Mapped[str] = mapped_column(Text, deferred=True)


class FileAsset(Base):
    __tablename__ = "file_asset"
    __table_args__ = (UniqueConstraint("owner_id", "sha256", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(150))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int]
