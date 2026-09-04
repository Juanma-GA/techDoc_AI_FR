"""SQLAlchemy 2.0 models pour le squelette XML Proofreader.

`AppConfig` (key/value) pour la config runtime (notamment la cle Mistral),
et `User` pour les comptes locaux (profils par poste, sans SSO). Chaque POC
ajoute ses propres tables ici.
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")


class User(Base):
    """Local account (per-workstation profile, no SSO/session). The password
    hash+salt never leave the backend: the API only ever returns id/name/
    email/created_at (see `schemas.UserOut`)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: "u_" + uuid.uuid4().hex[:12]
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time() * 1000))
