"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    llm: str


# ----- Settings (Mistral runtime config) ------------------------------------


class SettingsIn(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    chat_model: Optional[str] = None
    embed_model: Optional[str] = None
    llm_enabled: Optional[bool] = None


class SettingsOut(BaseModel):
    api_key_set: bool
    base_url: str
    chat_model: str
    embed_model: str
    llm_enabled: bool
    llm_tested: bool = False


class TestConnectionOut(BaseModel):
    ok: bool
    models: list[str] = Field(default_factory=list)
    error: Optional[str] = None


# ----- Admin (stats + reset) ------------------------------------------------


class AdminStatsOut(BaseModel):
    """Compteurs sommaires affiches dans l'onglet Donnees."""

    total: int = 0
    validated: int = 0
    refused: int = 0
    pending: int = 0


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]


# ----- BRDPs -----------------------------------------------------------------


class BrdpIn(BaseModel):
    id: str
    identifier: Optional[str] = None
    title: Optional[str] = ""
    definition: Optional[str] = ""
    proposal: Optional[str] = ""
    validation: Optional[str] = "Pending"
    comments: Optional[str] = None
    comment: Optional[str] = None
    history: Optional[list[dict[str, Any]]] = None


class BrdpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    identifier: str
    title: str
    definition: str
    proposal: str
    validation: str
    comments: str
    comment: str = ""
    history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ----- Notes ------------------------------------------------------------------


class NoteOut(BaseModel):
    text: str = ""


class NoteIn(BaseModel):
    text: str = ""


# ----- Project config ---------------------------------------------------------


class ProjectConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_name: str = ""
    model_ident_code: str = ""
    system_diff_code: str = "A"
    issue_number: str = "001"
    in_work: str = "00"
    language_iso: str = "en"
    country_iso: str = "US"
    security_classification: str = "01"
    enterprise_code: str = ""


class ProjectConfigIn(BaseModel):
    project_name: Optional[str] = None
    model_ident_code: Optional[str] = None
    system_diff_code: Optional[str] = None
    issue_number: Optional[str] = None
    in_work: Optional[str] = None
    language_iso: Optional[str] = None
    country_iso: Optional[str] = None
    security_classification: Optional[str] = None
    enterprise_code: Optional[str] = None


# ----- LLM proxy (chat / generation) -------------------------------------------


class ChatMessage(BaseModel):
    role: str
    content: str


class LlmChatIn(BaseModel):
    messages: list[ChatMessage]
    system: Optional[str] = None
    temperature: float = 0.3


class LlmChatOut(BaseModel):
    role: str = "assistant"
    content: str
    skipped: bool = False

