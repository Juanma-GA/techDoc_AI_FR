"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.flow.model import FlowGraph


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    llm: str


# ----- Settings (Mistral runtime config) ------------------------------------


class SettingsIn(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    chat_model: str | None = None
    embed_model: str | None = None
    llm_enabled: bool | None = None
    demo_enabled: bool | None = None


class SettingsOut(BaseModel):
    api_key_set: bool
    base_url: str
    chat_model: str
    embed_model: str
    llm_enabled: bool
    llm_tested: bool = False
    demo_enabled: bool = False


class TestConnectionOut(BaseModel):
    ok: bool
    models: list[str] = Field(default_factory=list)
    error: str | None = None


# ----- Admin (stats + reset) ------------------------------------------------


class AdminStatsOut(BaseModel):
    """Compteurs sommaires affiches dans l'onglet Donnees."""

    flows: int = 0
    nodes: int = 0
    edges: int = 0


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]


# ----- Flows ----------------------------------------------------------------


class FlowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: Literal["text", "table", "json", "dsl"] = "json"
    source_text: str = Field(default="", max_length=200_000)
    graph: FlowGraph


class FlowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    source_type: Literal["text", "table", "json", "dsl"] | None = None
    source_text: str | None = Field(default=None, max_length=200_000)
    graph: FlowGraph | None = None


class FlowSummary(BaseModel):
    id: str
    name: str
    source_type: str
    node_count: int
    edge_count: int
    created_at: datetime
    updated_at: datetime


class FlowOut(FlowSummary):
    source_text: str
    graph: FlowGraph


class ParseTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


class ParseJsonIn(BaseModel):
    content: str = Field(min_length=1, max_length=200_000)


class ParseResultOut(BaseModel):
    graph: FlowGraph
    warnings: list[str] = Field(default_factory=list)
    llm_used: bool = False


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class AssistantDocument(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=50_000)


class AssistantChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    graph: FlowGraph | None = None
    documents: list[AssistantDocument] = Field(default_factory=list, max_length=10)


class AssistantAttachOut(BaseModel):
    kind: Literal["graph", "document"]
    name: str
    graph: FlowGraph | None = None
    text: str = ""
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class AssistantChatOut(BaseModel):
    message: str
    graph: FlowGraph | None = None
    changed: bool = False
    llm_used: bool = False
    warnings: list[str] = Field(default_factory=list)
