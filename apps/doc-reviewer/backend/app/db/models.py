"""SQLAlchemy 2.0 models for doc-reviewer.

Domain entities:

- `Standard`         — a documentation/maintenance standard (S1000D, MAT10000…).
- `StandardVersion`  — a frozen version of a Standard with its built-in catalog.
- `Document`         — uploaded PDF + storage layout, current edited version.
- `AnalysisRun`      — one analysis pass over a document.
- `Suggestion`       — anomaly + structured replacement (original/proposed/bbox).
- `Rule`             — user-defined custom rule (regex, structural…).
- `EditHistory`      — audit log of patches applied to the PDF (rollback-aware).
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
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid4() -> uuid.UUID:
    return uuid.uuid4()


class Standard(Base):
    __tablename__ = "standards"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    builtin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    versions: Mapped[list["StandardVersion"]] = relationship(
        back_populates="standard", cascade="all, delete-orphan"
    )


class StandardVersion(Base):
    __tablename__ = "standard_versions"
    __table_args__ = (UniqueConstraint("standard_id", "label", name="uq_standard_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    standard_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    builtin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    catalog_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    disabled_rule_codes: Mapped[str] = mapped_column(
        Text, default="[]", server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    standard: Mapped[Standard] = relationship(back_populates="versions")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_dir: Mapped[str] = mapped_column(String(1000), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    target_unit_system: Mapped[str] = mapped_column(
        String(20), default="auto", server_default="auto"
    )
    standard_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("standard_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    standard_version_ids: Mapped[str] = mapped_column(
        Text, default="[]", server_default="[]"
    )
    status: Mapped[str] = mapped_column(
        String(30), default="uploaded", server_default="uploaded", index=True
    )
    current_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Format source fourni par l'utilisateur; le routage se fait via
    # `working_format` et non via ce champ.
    source_format: Mapped[str] = mapped_column(String(10), default="pdf", server_default="pdf")
    working_format: Mapped[str] = mapped_column(String(10), default="pdf", server_default="pdf")
    original_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    original_storage_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    # Portail qualite (homogeneite tous formats) : moteur de normalisation
    # ("pdf" natif, "libreoffice", "word"), % de pages porteuses de texte, et
    # etat de revuabilite ("analyzable" | "degraded" | "unusable"). Renseignes
    # a l'upload par `quality_gate.assess`. cf. core/quality_gate.py.
    convert_engine: Mapped[str] = mapped_column(String(20), default="pdf", server_default="pdf")
    text_coverage: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    quality: Mapped[str] = mapped_column(
        String(20), default="analyzable", server_default="analyzable", index=True
    )
    # Mapping manuel par document (saisi par le relecteur) : les consignes de
    # checklist peuvent y faire reference (ex. « verifier que la date de
    # revision de la page de garde correspond a la date de revision saisie
    # ici ») — injecte dans le contexte du scan IA par `rules_engine`.
    meta_revision_date: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    meta_cmm_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    meta_first_issue_date: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    meta_revision_number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    meta_pnr_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    document_language: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    @property
    def has_applied_edits(self) -> bool:
        return self.current_version > 0

    suggestions: Mapped[list["Suggestion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    history: Mapped[list["EditHistory"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    standard_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("standard_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    standard_version_ids: Mapped[str] = mapped_column(
        Text, default="[]", server_default="[]"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running", server_default="running")
    summary: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    context_snapshot_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    compiled_rules_snapshot_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    snapshot_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    document: Mapped[Document] = relationship(back_populates="runs")
    suggestions: Mapped[list["Suggestion"]] = relationship(back_populates="run")


class Suggestion(Base):
    __tablename__ = "suggestions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("rules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rule_kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rule_code: Mapped[str] = mapped_column(String(80), nullable=False)
    # Provenance affichee dans la liste des anomalies : "norme" | "checklist" |
    # "regle" (custom deterministe) | "transverse" (unites/mise en page/vision).
    # Calculee a la materialisation par `rules_engine.classify_source`.
    source_kind: Mapped[str] = mapped_column(
        String(20), default="norme", server_default="norme", index=True
    )
    severity: Mapped[str] = mapped_column(
        String(20), default="warning", server_default="warning"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    proposed_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    page: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    bbox: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    span_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Pipeline docx natif : identifiant de bloc cible ("dp<N>", cf. docx_parser).
    # NULL pour les suggestions PDF (localisees par bbox). `span_index` sert
    # d'occurrence dans le bloc a l'edition.
    target_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="open", server_default="open", index=True
    )
    # Motif libre saisi par le relecteur au rejet (faux positif, hors perimetre...).
    # Alimente la memoire de rejet : une anomalie rejetee n'est plus re-signalee.
    feedback: Mapped[str] = mapped_column(Text, default="", server_default="")
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    document: Mapped[Document] = relationship(back_populates="suggestions")
    run: Mapped[Optional[AnalysisRun]] = relationship(back_populates="suggestions")


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    replacement: Mapped[str] = mapped_column(Text, default="", server_default="")
    severity: Mapped[str] = mapped_column(
        String(20), default="warning", server_default="warning"
    )
    message: Mapped[str] = mapped_column(Text, default="", server_default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    standard_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("standard_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class CompiledRuleVersion(Base):
    __tablename__ = "compiled_rule_versions"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_compiled_rule_code_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    compiled_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    validation_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class EditHistory(Base):
    __tablename__ = "edit_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    suggestion_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("suggestions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_before: Mapped[int] = mapped_column(Integer, nullable=False)
    version_after: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    diff_summary: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    document: Mapped[Document] = relationship(back_populates="history")


class AppConfig(Base):
    """Key/value store for runtime config (Mistral API key, etc.)."""

    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")
