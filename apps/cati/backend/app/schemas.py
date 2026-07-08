"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


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

    documents: int = 0
    items: int = 0
    total_size_bytes: int = 0


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]


# ----- CATI : documents + items (nomenclature) ------------------------------


class HeaderMeta(BaseModel):
    """Metadonnees document (bloc en-tete module), saisies dans l'UI."""

    module: str = ""
    otan_supplier: str = ""
    drw: str = ""
    top_assembly: str = ""
    bom_title: str = ""


class ChallengeIssue(BaseModel):
    field: str
    deterministic: str
    llm: str


class ChallengeRow(BaseModel):
    fig: str
    verdict: str  # ok | warning | missing | extra
    issues: list[ChallengeIssue] = Field(default_factory=list)
    llm_only: Optional[dict[str, str]] = None


class ChallengeSummary(BaseModel):
    ok: int = 0
    warning: int = 0
    missing: int = 0
    extra: int = 0
    total: int = 0
    clean: bool = False


class ChallengeReport(BaseModel):
    status: str = "none"  # none | done | skipped
    reason: Optional[str] = None
    method: Optional[str] = None
    summary: ChallengeSummary = Field(default_factory=ChallengeSummary)
    rows: list[ChallengeRow] = Field(default_factory=list)


class DocumentOut(BaseModel):
    id: str
    filename: str
    size: int
    page_count: int
    status: str
    extraction_method: str
    item_count: int
    profile_id: Optional[str] = None
    header_meta: HeaderMeta
    warnings: list[str] = Field(default_factory=list)
    challenge: ChallengeReport = Field(default_factory=ChallengeReport)
    error: Optional[str] = None
    created_at: str


class UploadItemResult(BaseModel):
    filename: str
    document_id: Optional[str] = None
    status: str  # created | duplicate | error
    item_count: int = 0
    error: Optional[str] = None


class UploadResultOut(BaseModel):
    results: list[UploadItemResult]


class ItemOut(BaseModel):
    id: str
    order_index: int
    source_page: Optional[int] = None
    fields: dict[str, object]
    included: bool
    edited: bool


class ItemsOut(BaseModel):
    document_id: str
    method: str
    warnings: list[str] = Field(default_factory=list)
    items: list[ItemOut]


class ItemPatch(BaseModel):
    fields: Optional[dict[str, object]] = None
    included: Optional[bool] = None


class ItemCreate(BaseModel):
    fields: dict[str, object] = Field(default_factory=dict)
    after_id: Optional[str] = None


class ReorderIn(BaseModel):
    ordered_ids: list[str]


# ----- CATI : templates Excel de sortie -------------------------------------


class TemplateOut(BaseModel):
    id: str
    name: str
    filename: str
    sheet_name: str
    header_row: int
    data_start_row: int
    is_default: bool
    header_columns: list[str] = Field(default_factory=list)
    created_at: str


# ----- CATI : profils (detection PDF + mapping Excel + template) -------------


class ProfileIn(BaseModel):
    name: str
    template_id: Optional[str] = None
    pdf_map: dict[str, int] = Field(default_factory=dict)
    excel_map: dict[str, str] = Field(default_factory=dict)


class ProfileOut(BaseModel):
    id: str
    name: str
    is_default: bool
    template_id: Optional[str] = None
    pdf_map: dict[str, int] = Field(default_factory=dict)
    excel_map: dict[str, str] = Field(default_factory=dict)
    created_at: str
