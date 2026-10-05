"""SQLAlchemy 2.0 models pour ECM-rename.

`AppConfig` stocke la configuration runtime et `PathPreference` les derniers
chemins source, tracker et sortie dans SQLite.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")


class PathPreference(Base):
    __tablename__ = "path_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1, server_default="1")
    source_path: Mapped[str] = mapped_column(Text, default="", server_default="")
    tracker_path: Mapped[str] = mapped_column(Text, default="", server_default="")
    output_path: Mapped[str] = mapped_column(Text, default="", server_default="")
