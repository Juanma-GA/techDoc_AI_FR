"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

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
    llm_confidence_threshold: Optional[float] = None


class SettingsOut(BaseModel):
    api_key_set: bool
    base_url: str
    chat_model: str
    embed_model: str
    llm_enabled: bool
    llm_tested: bool = False
    llm_confidence_threshold: float = 0.7


class TestConnectionOut(BaseModel):
    ok: bool
    models: list[str] = Field(default_factory=list)
    error: Optional[str] = None


# ----- Admin (stats + reset) ------------------------------------------------


class AdminStatsOut(BaseModel):
    """Compteurs sommaires affiches dans l'onglet Donnees du preview."""

    documents: int = 0
    batches: int = 0
    suggestions: int = 0
    rules: int = 0
    standards: int = 0
    total_size_bytes: int = 0


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]


# ----- Standards & Rules ----------------------------------------------------


class StandardVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    builtin: bool
    rule_count: int = 0


class StandardOut(BaseModel):
    id: uuid.UUID
    code: str
    label: str
    description: Optional[str] = None
    builtin: bool
    versions: list[StandardVersionOut] = Field(default_factory=list)


class RuleIn(BaseModel):
    name: str
    category: str = ""
    kind: str
    pattern: str = ""
    replacement: str = ""
    target_zone: str = ""
    severity: str = "warning"
    message: str = ""
    enabled: bool = True
    validated: bool = True
    standard_version_id: Optional[uuid.UUID] = None


class RuleOut(RuleIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class RuleImportResult(BaseModel):
    mode: str = "replace"
    imported: int
    created: int = 0
    updated: int = 0
    replaced_count: int = 0
    by_kind: dict[str, int] = Field(default_factory=dict)
    skipped: list[str] = Field(default_factory=list)
    llm_used: bool = False


class SheetInfo(BaseModel):
    name: str
    header_row: int = 0  # ligne d'en-tete detectee (0-based)
    rows: list[list[str]] = Field(default_factory=list)  # grille d'apercu


class SheetInspectOut(BaseModel):
    sheets: list[SheetInfo] = Field(default_factory=list)


# ----- Catalogue (regles builtin d'une StandardVersion) ---------------------


class CatalogRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    code: str
    title: str = ""
    description: str = ""
    kind: str
    severity: str = "warning"
    pattern: str = ""
    replacement: str = ""
    message: str = ""
    example_invalid: str = ""
    example_valid: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)
    source: str = ""  # origine affichee : "ATA 100", "CMM", "Ajoutee"...


class CatalogRuleIn(BaseModel):
    code: str
    title: str = ""
    description: str = ""
    kind: str
    severity: str = "warning"
    pattern: str = ""
    replacement: str = ""
    message: str = ""
    example_invalid: str = ""
    example_valid: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class CatalogRulePatchIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    kind: Optional[str] = None
    severity: Optional[str] = None
    pattern: Optional[str] = None
    replacement: Optional[str] = None
    message: Optional[str] = None
    example_invalid: Optional[str] = None
    example_valid: Optional[str] = None
    metadata: Optional[dict[str, str]] = None


class CatalogToggleIn(BaseModel):
    code: str
    enabled: bool


class StandardVersionDetailOut(BaseModel):
    id: uuid.UUID
    label: str
    builtin: bool
    catalog: list[CatalogRuleOut] = Field(default_factory=list)
    disabled_rule_codes: list[str] = Field(default_factory=list)
    custom_rules: list["RuleOut"] = Field(default_factory=list)


# ----- Documents & Batches --------------------------------------------------


class DocumentOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    status: str
    block_count: int
    current_version: int
    batch_id: Optional[uuid.UUID] = None
    standard_version_ids: list[uuid.UUID] = Field(default_factory=list)
    created_at: datetime
    findings_total: int = 0  # nb d'anomalies (suggestions)
    findings_open: int = 0  # anomalies non traitees (status open)


class UploadResult(BaseModel):
    batch_id: uuid.UUID
    documents: list[DocumentOut] = Field(default_factory=list)
    ignored: list[str] = Field(default_factory=list)


class BatchOut(BaseModel):
    id: uuid.UUID
    label: str
    created_at: datetime
    documents: list[DocumentOut] = Field(default_factory=list)


class ExportZipRequest(BaseModel):
    document_ids: list[uuid.UUID] = Field(default_factory=list)


# ----- Suggestions ----------------------------------------------------------


class SuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    rule_kind: str
    rule_code: str
    category: str = ""  # Sujet (Rule.category / colonne TOPIC) ; "" si regle standard
    severity: str
    message: str
    original_text: str
    proposed_text: str
    target_id: str
    block_index: int
    zone: str
    semantic_zone: str
    char_start: int
    char_end: int
    span_index: int
    confidence: Optional[float] = None
    status: str
    applied_at: Optional[datetime] = None
    applied_version: Optional[int] = None
    created_at: datetime


class SuggestionPatchIn(BaseModel):
    status: Optional[str] = None
    proposed_text: Optional[str] = None
    feedback_note: Optional[str] = None


class AnalyzeRequest(BaseModel):
    standard_version_ids: Optional[list[uuid.UUID]] = None


# ----- Vue document (rendu HTML + surlignage) -------------------------------


class ViewBlock(BaseModel):
    target_id: str
    kind: str  # paragraph | heading | cell
    zone: str  # body | header | footer
    semantic_zone: str = ""
    heading_level: Optional[int] = None
    text: str
    table_id: Optional[int] = None
    row: Optional[int] = None
    col: Optional[int] = None
    page: int = 1


class DocumentViewOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    current_version: int
    blocks: list[ViewBlock] = Field(default_factory=list)


class HighlightBox(BaseModel):
    left: float
    top: float
    width: float
    height: float


class SuggestionHighlight(BaseModel):
    id: str
    page: int
    boxes: list[HighlightBox] = Field(default_factory=list)


class PdfViewOut(BaseModel):
    available: bool = True  # False si LibreOffice absent -> le front retombe sur le HTML
    page_count: int = 0
    highlights: list[SuggestionHighlight] = Field(default_factory=list)


class LayoutFindingOut(BaseModel):
    id: str
    rule_code: str
    severity: str
    message: str
    page: int
    boxes: list[HighlightBox] = Field(default_factory=list)


class LayoutChecksOut(BaseModel):
    available: bool = True
    findings: list[LayoutFindingOut] = Field(default_factory=list)


# ----- Dashboard ------------------------------------------------------------


class DashboardTopDoc(BaseModel):
    id: uuid.UUID
    original_filename: str
    open_count: int


class DashboardOut(BaseModel):
    documents: int = 0
    batches: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_kind: dict[str, int] = Field(default_factory=dict)
    by_topic: dict[str, int] = Field(default_factory=dict)
    top_documents: list[DashboardTopDoc] = Field(default_factory=list)
