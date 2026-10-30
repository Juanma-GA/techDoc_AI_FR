"""SQLAlchemy 2.0 models pour s1000d-extractor.

- `AppConfig`    : key/value runtime (cle Mistral). Preserve par les resets.
- `BrexProfile`  : un BREX projet reutilisable (uploade une fois, applique a
  tous les documents du projet -> evite le remapping par document).
- `Document`     : un document source (PDF/DOCX) et le resultat de sa migration
  (arbre IR + XML S1000D + violations).

Types choisis SQLite ET Postgres-compatibles (String/Text/DateTime/Integer).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")


class BrexProfile(Base):
    __tablename__ = "brex_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    s1000d_issue: Mapped[str] = mapped_column(String(10))
    xml_path: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(500))
    source_format: Mapped[str] = mapped_column(String(10))          # "pdf" | "docx"
    s1000d_issue: Mapped[str] = mapped_column(String(10), default="4.2")
    context_hint: Mapped[str] = mapped_column(String(20), default="mixed")
    brex_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("brex_profiles.id", ondelete="SET NULL"), nullable=True
    )
    storage_path: Mapped[str] = mapped_column(String(1000))
    pdf_cut_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    pdf_cut_start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_cut_end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    xml_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="uploaded", index=True)
    dm_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ir_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    violations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Wizard (configuration etape par etape) :
    wizard_step: Mapped[str | None] = mapped_column(String(20), nullable=True)
    split_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dms_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Pile d'annulation (undo) des editions de decoupage : liste JSON
    # d'instantanes `dms_json` successifs (bornee cote code).
    dms_history_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    preliminary_review_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ressources client optionnelles : DMRL (decoupage impose + PMC), CIR
    # (contenus partages), regles client BREX JSON.
    dmrl_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    dmrl_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    dm_header_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    dm_header_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cir_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    brex_rules_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DmDocumentLink(Base):
    """
    Link DMRL line to extracted Data Module.

    Enables:
    - Auto-linking (one DMRL row → one DM file)
    - Manual link edits (user maps DMRL to DM)
    - Traceability (which DMRL line generated which DM)
    """

    __tablename__ = "dm_document_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    doc_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    dmrl_line_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )  # DMRL unique ID (if provided)
    dm_code: Mapped[str] = mapped_column(
        String(100), index=True
    )  # Data Module code (e.g., "DMC-ABC-123-00A-001A-001-A")
    auto_linked: Mapped[bool] = mapped_column(default=True)  # True if auto-linked from DMRL
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DmVersion(Base):
    """
    Track DM evolution: content changes, author, timestamp, status.

    Enables:
    - Versioning: restore previous DM versions
    - Audit trail: who changed what, when
    - Diff UI: compare versions
    """

    __tablename__ = "dm_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    doc_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    dm_code: Mapped[str] = mapped_column(String(100), index=True)
    # XML content of the Data Module
    content: Mapped[str] = mapped_column(Text)
    # Metadata
    author: Mapped[str] = mapped_column(String(100), default="unknown")
    # Status: "draft", "extracted", "validated", "frozen"
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # User notes/commit message
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
