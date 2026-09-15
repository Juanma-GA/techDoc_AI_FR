"""SQLAlchemy 2.0 models pour doc-writer.

Cinq entités :
- Document          : un fichier uploadé, parsé une fois, indexé une fois
- DocumentChunk     : un morceau de texte du document + son embedding Mistral
- Session           : un fil de génération multi-tours
- Message           : un message (user / assistant) d'une session
- AppConfig         : key/value pour la config runtime (clés Mistral)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _now_local() -> datetime:
    """Heure locale systeme (naive). POC local-first mono-machine : on stocke
    l'heure murale locale pour que l'UI l'affiche telle quelle. SQLite ne
    conserve pas le fuseau ; un timestamp UTC serialise sans offset etait
    interprete comme heure locale cote JS -> decalage du fuseau a l'affichage.
    """
    return datetime.now()


def _uuid4() -> uuid.UUID:
    return uuid.uuid4()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), default="", server_default="")
    size: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # MFA pilot (R1, §3) : plus `unique=True` a elle seule -- deux utilisateurs
    # differents peuvent uploader le meme contenu (meme sha256) sans collision.
    # L'unicite devient composite (user_email, sha256), cf. __table_args__.
    # Index simple conserve pour les lookups (dedup scope par utilisateur).
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    index_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # source = contenu input pour RAG ; template = structure {{placeholders}} a remplir ;
    # style = exemple de syntaxe / ton a reproduire.
    kind: Mapped[str] = mapped_column(String(16), default="source", server_default="source", nullable=False)
    # MFA pilot (R1, §3) : proprietaire du document, email normalise (minuscules)
    # -- cle de jointure avec AUTHDB (app.core.auth_db.normalize_email). Nullable
    # tant que auth_enabled=False (tier1 local, mono-utilisateur implicite) ;
    # backfille vers `settings.legacy_user_email` par la migration 0003 sur une
    # base existante.
    user_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_local)

    __table_args__ = (
        UniqueConstraint("user_email", "sha256", name="uq_documents_user_email_sha256"),
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    title: Mapped[str] = mapped_column(String(255), default="", server_default="")
    # JSON list of doc UUIDs (kind=source). Chaîne vide ou "[]" = AUCUNE source :
    # génération libre depuis le seul brief (cf. writer_engine.build_messages).
    scope_doc_ids: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    lang: Mapped[str] = mapped_column(String(8), default="fr", server_default="fr")
    # Options de generation (cf. core/writer_engine.py FORMAT_PROMPTS / LENGTH_HINTS / TONE_HINTS).
    output_format: Mapped[str] = mapped_column(String(32), default="markdown", server_default="markdown", nullable=False)
    length: Mapped[str] = mapped_column(String(16), default="medium", server_default="medium", nullable=False)
    tone: Mapped[str] = mapped_column(String(32), default="professional", server_default="professional", nullable=False)
    # Doc references optionnelles : template a remplir + style a reproduire.
    template_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    style_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    # MFA pilot (R1, §3) : meme raisonnement que Document.user_email.
    # `Message` n'a PAS sa propre colonne : un message appartient a une
    # session, donc herite de son proprietaire via session_id -- pas de
    # redondance a synchroniser.
    user_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_local)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, default="", server_default="")
    citations: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_local)

    session: Mapped[Session] = relationship(back_populates="messages")


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")
