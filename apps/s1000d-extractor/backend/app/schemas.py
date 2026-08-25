"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    error: str | None = None


# ----- Admin (stats + reset) ------------------------------------------------


class AdminStatsOut(BaseModel):
    """Compteurs sommaires affiches dans l'onglet Donnees du preview.

    Les champs sont volontairement generiques : chaque POC peut surcharger
    `admin.stats()` pour compter ses propres tables. Pour le _template,
    tout est a 0.
    """

    documents: int = 0
    extracted: int = 0
    brex_profiles: int = 0
    total_size_bytes: int = 0


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]


# ----- S1000D extraction -----------------------------------------------------


class BrexProfileOut(BaseModel):
    id: str
    name: str
    s1000d_issue: str
    created_at: str


class DocumentOut(BaseModel):
    id: str
    filename: str
    source_format: str
    s1000d_issue: str
    context_hint: str
    status: str
    dm_type: str | None = None
    page_count: int | None = None
    has_xml: bool = False
    violation_count: int = 0
    created_at: str


class ViolationOut(BaseModel):
    severity: str          # "error" | "warning" | "info"
    rule: str              # "WELLFORMED" | "XSD" | "BREX"
    message: str
    path: str = "/"


class ExtractDoneOut(BaseModel):
    document_id: str
    dm_type: str
    tree: dict
    violations: list[ViolationOut] = Field(default_factory=list)


class NodeOverrideIn(BaseModel):
    element: str = Field(..., description="Element S1000D a forcer pour ce noeud.")


# ----- DMRL Linking & Versioning -----------------------------------------------


class DmDocumentLinkOut(BaseModel):
    """Link between a DMRL line and an extracted Data Module."""

    id: str
    doc_id: str
    dmrl_line_id: str | None = None
    dm_code: str
    auto_linked: bool
    created_at: str


class DmVersionOut(BaseModel):
    """Data Module version snapshot (for audit trail / restore)."""

    id: str
    doc_id: str
    dm_code: str
    author: str
    status: str  # "draft", "extracted", "validated", "frozen"
    notes: str | None = None
    created_at: str
    content_length: int  # size of content in bytes


class DmVersionContentOut(BaseModel):
    """Full Data Module version with content (for restore / diff)."""

    id: str
    doc_id: str
    dm_code: str
    content: str  # XML
    author: str
    status: str
    notes: str | None = None
    created_at: str


class LinkDmrlIn(BaseModel):
    """Request to link DMRL to Data Modules (auto or manual)."""

    mode: str = "auto"  # "auto" | "manual"
    dmrl_links: list[dict] = Field(default_factory=list)  # [{"dmrl_line_id": "...", "dm_code": "..."}]
