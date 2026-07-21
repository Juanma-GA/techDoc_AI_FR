"""SQLAlchemy 2.0 models for Corpus Agent v3.

Migrated from legacy/ftm-v1/FTM Agent/backend/app/db/models.py with three
notable changes:

- **UUID v4 primary keys** (was: int auto-increment) — STANDARD §2.3.
- **Modern SQLAlchemy 2.0 style** (`Mapped`, `mapped_column`).
- **Timestamps in UTC** via `datetime.now(timezone.utc)` (replaces the
  deprecated `datetime.utcnow`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid4() -> uuid.UUID:
    return uuid.uuid4()


# =============================================================================
# Projects & files
# =============================================================================


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    vision_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Suivi ATM FTM : script (colonne BF), granules (BH/BJ). NULL = checks
    # script/granule à référence externe silencieusement skippés.
    reference_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Registre des colonnes de référence — liste JSON
    # [{"name","sheet","column","builtin"}]. Les 3 builtin (script,
    # granule_defaut, granule_pose) alimentent les checks script/granule ;
    # les autres sont appelables via {nom} dans les règles personnalisées.
    # NULL = checks à référence externe sur défauts rules.json.
    reference_columns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Ligne d'en-tête choisie par onglet du référentiel — JSON {onglet: ligne(1-based)}.
    # Lue pour afficher les bons libellés de colonnes dans l'éditeur de mapping
    # quand l'en-tête n'est pas la ligne la plus large (détection auto en défaut).
    # NULL = détection auto (_detect_header_row).
    reference_header_rows: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # BASL : référence des rechanges / outillages / infrastructure / en-tête.
    # NULL = cross-checks BASL skippés.
    basl_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Registre des colonnes BASL — liste JSON [{"name","sheet","column","builtin"}].
    # Mêmes sémantiques que `reference_columns`, mais pour la BASL. Les 3 builtin
    # (rechange, outillage, infrastructure) ciblent les colonnes contre lesquelles
    # le check « référentiel » cross-checke le livrable. NULL ou colonne non
    # mappée = repli sur l'union de toutes les cellules de la BASL (compat.).
    basl_columns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Ligne d'en-tête choisie par onglet de la BASL — JSON {onglet: ligne(1-based)}.
    # NULL = détection auto. Aligne les libellés de colonnes dans l'éditeur de mapping.
    basl_header_rows: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    files: Mapped[list["File"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    anomalies: Mapped[list["Anomaly"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_name: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    project: Mapped[Project] = relationship(back_populates="files")
    versions: Mapped[list["FileVersion"]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FileVersion.uploaded_at",
    )


class FileVersion(Base):
    __tablename__ = "file_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    extracted_text: Mapped[str] = mapped_column(Text, default="", server_default="")

    file: Mapped[File] = relationship(back_populates="versions")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="file_version", cascade="all, delete-orphan"
    )
    anomalies: Mapped[list["Anomaly"]] = relationship(
        back_populates="file_version", cascade="all, delete-orphan"
    )


# =============================================================================
# Analysis & anomalies
# =============================================================================


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("file_versions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Categorie metier = « Sujet » de la regle checklist a l'origine de l'anomalie.
    # Dimension de regroupement des KPI (le type est toujours `personnalisee`).
    category: Mapped[str] = mapped_column(String(120), default="", server_default="", index=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium", server_default="medium")
    # Niveau de confiance dans la recommandation : elevee | moyenne | faible.
    # Déterministe → elevee ; jugement IA → renvoyé par Mistral.
    confidence: Mapped[str] = mapped_column(String(20), default="elevee", server_default="elevee")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Clés i18n + params JSON pour rendu côté front : si `message_key` est
    # présent, le front résout `t(message_key, params)` et utilise `message`
    # comme fallback. Pareil pour `suggestion_key`. NULL = anomalie pré-i18n
    # (rendu FR brut via `message` / `suggestion`).
    message_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message_params_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggestion_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    suggestion_params_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[str] = mapped_column(String(500), default="", server_default="")
    status: Mapped[str] = mapped_column(String(30), default="open", server_default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="anomalies")
    file_version: Mapped[Optional[FileVersion]] = relationship(back_populates="anomalies")
    run: Mapped[Optional["AnalysisRun"]] = relationship(back_populates="anomalies")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running", server_default="running")
    summary: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")

    project: Mapped[Project] = relationship(back_populates="runs")
    anomalies: Mapped[list[Anomaly]] = relationship(back_populates="run")


# =============================================================================
# RAG / chat
# =============================================================================


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    file_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("file_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    section: Mapped[str] = mapped_column(String(255), default="", server_default="")

    file_version: Mapped[FileVersion] = relationship(back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    # Nullable depuis la migration multi-scope ; conservé pour compat
    # (= projet « principal » d'une session mono-projet).
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # JSON list of UUIDs. [] = tous les projets. [uuid] = un projet.
    # [uuid1, uuid2, …] = plusieurs projets (subset).
    scope_project_ids: Mapped[str] = mapped_column(
        Text, default="[]", server_default="[]", nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), default="Nouvelle conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    project: Mapped[Optional[Project]] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


# =============================================================================
# App-level config (key/value)
# =============================================================================


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")
