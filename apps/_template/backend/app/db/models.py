"""SQLAlchemy 2.0 models pour le squelette TEMPLATE.

Une seule table de base : `AppConfig` (key/value) pour la config runtime
(notamment la cle Mistral). Chaque POC ajoute ses propres tables ici.
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")
