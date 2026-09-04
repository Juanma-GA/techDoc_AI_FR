"""SQLAlchemy 2.0 models pour OCR Vision.

Base : `AppConfig` (key/value) pour la config runtime (cle Mistral, flags).

Capitalisation des donnees extraites :
- `TableTemplate` : definition REUTILISABLE d'une table (colonnes + regles
  d'extraction), applicable a plusieurs projets.
- `Project` : unite de capitalisation.
- `ProjectTable` : instance d'un template dans un projet ; porte un snapshot
  des colonnes (fige l'extraction/export si le template evolue ensuite) et les
  lignes extraites. C'est « la table » qu'on exporte en CSV.
- `ExtractedRow` : une ligne extraite d'un document OCRise.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")


class TableTemplate(Base):
    """Definition reutilisable : nom + colonnes `[{key,label,type,rule}]`."""

    __tablename__ = "table_template"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Liste de ColumnSpec : {"key","label","type","rule"}. type in text|number|date|bool.
    columns: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "project"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectTable(Base):
    """Template applique a un projet ; porte les lignes extraites."""

    __tablename__ = "project_table"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[str] = mapped_column(ForeignKey("table_template.id"))
    name: Mapped[str] = mapped_column(String(200))
    # Snapshot des colonnes au moment du rattachement (fige extraction + export).
    columns: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExtractedRow(Base):
    __tablename__ = "extracted_row"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_table_id: Mapped[str] = mapped_column(
        ForeignKey("project_table.id", ondelete="CASCADE"), index=True
    )
    source_filename: Mapped[str] = mapped_column(String(500), default="", server_default="")
    # Valeurs extraites : {column_key: value}.
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExtractedImage(Base):
    """Image/illustration extraite d'un PDF (fichier JPG sur disque)."""

    __tablename__ = "extracted_image"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_table_id: Mapped[str] = mapped_column(
        ForeignKey("project_table.id", ondelete="CASCADE"), index=True
    )
    source_filename: Mapped[str] = mapped_column(String(500), default="", server_default="")
    # Nom du fichier stocke sous data/storage/<project_table_id>/.
    filename: Mapped[str] = mapped_column(String(300))
    page: Mapped[int | None] = mapped_column(default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
