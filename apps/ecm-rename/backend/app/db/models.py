"""SQLAlchemy models for ECM-rename path preferences."""

from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PathPreference(Base):
    __tablename__ = "path_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1, server_default="1")
    source_path: Mapped[str] = mapped_column(Text, default="", server_default="")
    tracker_path: Mapped[str] = mapped_column(Text, default="", server_default="")
    output_path: Mapped[str] = mapped_column(Text, default="", server_default="")
