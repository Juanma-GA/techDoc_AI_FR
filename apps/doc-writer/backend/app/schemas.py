"""Pydantic v2 I/O schemas — un modèle par body / response."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ----- Health ----------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    llm: str


# ----- Documents -------------------------------------------------------------


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str
    size: int
    sha256: str
    chunk_count: int
    index_error: Optional[str] = None
    kind: str = "source"  # source | template | style
    uploaded_at: datetime


class ZoneOut(BaseModel):
    id: str
    kind: str          # "placeholder" | "xxx" | "llm"
    slide_index: int
    slide_title: str
    label: str
    location: str
    target: str = ""   # Pour kind="llm" : path encode vers shape/cellule.


class ZonesOut(BaseModel):
    zones: list[ZoneOut]
    llm_used: bool = False


class UploadItemResult(BaseModel):
    filename: str
    ok: bool
    document_id: Optional[uuid.UUID] = None
    skipped: Optional[str] = None
    error: Optional[str] = None
    chunk_count: Optional[int] = None


class UploadResultOut(BaseModel):
    uploaded: list[UploadItemResult]


# ----- Sessions / Messages ---------------------------------------------------


class SessionCreateIn(BaseModel):
    title: Optional[str] = None
    scope_doc_ids: list[uuid.UUID] = Field(default_factory=list)
    lang: str = "fr"
    output_format: str = "markdown"  # markdown | faq | structured | table | template
    length: str = "medium"           # short | medium | long
    tone: str = "professional"       # professional | pedagogical | technical | synthetic
    template_doc_id: Optional[uuid.UUID] = None
    style_doc_id: Optional[uuid.UUID] = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    scope_doc_ids: list[uuid.UUID]
    lang: str
    output_format: str = "markdown"
    length: str = "medium"
    tone: str = "professional"
    template_doc_id: Optional[uuid.UUID] = None
    style_doc_id: Optional[uuid.UUID] = None
    created_at: datetime

    @field_validator("scope_doc_ids", mode="before")
    @classmethod
    def _parse_scope(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                raw = json.loads(v or "[]")
            except json.JSONDecodeError:
                return []
            if not isinstance(raw, list):
                return []
            out: list[str] = []
            for s in raw:
                try:
                    out.append(str(uuid.UUID(s)))
                except (ValueError, TypeError):
                    continue
            return out
        return v


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    citations: list[dict[str, Any]]
    created_at: datetime

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                raw = json.loads(v or "[]")
            except json.JSONDecodeError:
                return []
            return raw if isinstance(raw, list) else []
        return v


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)


# ----- Settings --------------------------------------------------------------


class SettingsIn(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    chat_model: Optional[str] = None
    embed_model: Optional[str] = None


class SettingsOut(BaseModel):
    api_key_set: bool
    base_url: str
    chat_model: str
    embed_model: str


class TestConnectionOut(BaseModel):
    ok: bool
    models: list[str] = Field(default_factory=list)
    error: Optional[str] = None


# ----- Admin -----------------------------------------------------------------


class AdminStatsOut(BaseModel):
    documents: int
    chunks: int
    sessions: int
    messages: int
    total_size_bytes: int


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]
