"""Pydantic v2 I/O schemas for doc-reviewer."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Documents
# =============================================================================


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    sha256: str
    page_count: int
    target_unit_system: str
    standard_version_id: Optional[uuid.UUID] = None
    standard_version_ids: list[uuid.UUID] = Field(default_factory=list)
    status: str
    current_version: int
    has_applied_edits: bool = False
    # Format source fourni par l'utilisateur, puis format interne choisi automatiquement.
    source_format: str = "pdf"
    working_format: str = "pdf"
    original_sha256: Optional[str] = None
    # Portail qualite (revuabilite homogene tous formats).
    convert_engine: str = "pdf"
    text_coverage: int = 100
    quality: str = "analyzable"
    client_metadata: dict[str, Any] = Field(default_factory=dict)
    # Mapping manuel par document, reference par les consignes de checklist.
    meta_revision_date: Optional[str] = None
    meta_cmm_number: Optional[str] = None
    meta_first_issue_date: Optional[str] = None
    meta_last_issue_date: Optional[str] = None
    meta_revision_number: Optional[str] = None
    meta_pnr_number: Optional[str] = None
    meta_manufacturer: Literal["Airbus", "Boeing"] = "Airbus"
    document_language: Optional[Literal["fr", "en"]] = None
    created_at: datetime

    @field_validator("standard_version_ids", mode="before")
    @classmethod
    def _parse_ids(cls, v: object) -> object:
        if isinstance(v, str):
            try:
                parsed = json.loads(v or "[]")
            except json.JSONDecodeError:
                return []
            return parsed if isinstance(parsed, list) else []
        return v


class RollbackIn(BaseModel):
    target_version: int = Field(..., ge=0)


class DocumentMetaPatchIn(BaseModel):
    """Mapping manuel par document — champs libres references par les
    consignes de checklist (ex. « verifier la date de revision »)."""

    client_metadata: dict[str, Any] = Field(default_factory=dict)
    meta_revision_date: Optional[str] = Field(default=None, max_length=60)
    meta_cmm_number: Optional[str] = Field(default=None, max_length=120)
    meta_first_issue_date: Optional[str] = Field(default=None, max_length=60)
    meta_last_issue_date: Optional[str] = Field(default=None, max_length=60)
    meta_revision_number: Optional[str] = Field(default=None, max_length=60)
    meta_pnr_number: Optional[str] = Field(default=None, max_length=120)
    meta_manufacturer: Literal["Airbus", "Boeing"] = "Airbus"
    document_language: Optional[Literal["fr", "en"]] = None


class ChecklistContextIn(BaseModel):
    meta_revision_date: Optional[str] = Field(default=None, max_length=60)
    meta_cmm_number: Optional[str] = Field(default=None, max_length=120)
    meta_first_issue_date: Optional[str] = Field(default=None, max_length=60)
    meta_revision_number: Optional[str] = Field(default=None, max_length=60)
    document_language: Optional[Literal["fr", "en"]] = None


class ChecklistContextOut(ChecklistContextIn):
    pass


# =============================================================================
# Suggestions
# =============================================================================


class SuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    run_id: Optional[uuid.UUID]
    rule_kind: str
    rule_code: str
    source_kind: str = "norme"
    severity: str
    message: str
    original_text: str
    proposed_text: str
    page: int
    bbox: dict[str, Any]  # may contain page_w/page_h/page_rotation alongside x0..y1
    span_index: int
    # Pipeline docx natif : bloc cible ("dp<N>"), NULL pour les suggestions PDF.
    target_id: Optional[str] = None
    status: str
    feedback: str = ""
    applied_at: Optional[datetime]
    applied_version: Optional[int]
    created_at: datetime

    @field_validator("bbox", mode="before")
    @classmethod
    def _parse_bbox(cls, v: object) -> object:
        if isinstance(v, str):
            try:
                return json.loads(v or "{}")
            except json.JSONDecodeError:
                return {}
        return v


class SuggestionPatchIn(BaseModel):
    status: Literal["open", "accepted", "edited", "rejected"]
    proposed_text: Optional[str] = None
    # Motif libre de rejet (corpus-agent-style). Surtout renseigne au rejet.
    feedback: Optional[str] = None


class SuggestionBulkStatusIn(BaseModel):
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    status: Literal["open", "accepted", "edited", "rejected"]
    feedback: Optional[str] = None


class SuggestionBulkStatusOut(BaseModel):
    updated: int
    status: str


class SuggestionApplyOut(BaseModel):
    suggestion_id: uuid.UUID
    document_id: uuid.UUID
    new_version: int
    snapshot_path: str
    font_used: str
    fallback_used: bool
    length_delta: int
    font_size_used: float = 0.0
    wrapped: bool = False


class SuggestionGroupApplyOut(BaseModel):
    """Result of applying the same anomaly across every page at once."""

    suggestion_id: uuid.UUID
    document_id: uuid.UUID
    new_version: int
    applied_count: int
    skipped_count: int
    applied_ids: list[uuid.UUID]
    pages: list[int]


# =============================================================================
# Rules
# =============================================================================


RuleKind = Literal[
    "regex_replace", "regex_flag", "term_replace",
    "case_capitalize", "accent_fix",
    "field_required", "section_required", "field_consistency",
    "step_pattern", "enum_value",
    # Checklist imports : consigne en langage naturel jugee par le LLM
    # (`llm_nl`) ou verification humaine hors IA (`manual`).
    "llm_nl", "manual",
]


class RuleIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    kind: RuleKind
    pattern: str = Field(..., min_length=1)
    replacement: str = ""
    severity: Literal["info", "warning", "error"] = "warning"
    message: str = ""
    enabled: bool = True
    standard_version_id: Optional[uuid.UUID] = None


class RulePatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    kind: Optional[RuleKind] = None
    pattern: Optional[str] = None
    replacement: Optional[str] = None
    severity: Optional[Literal["info", "warning", "error"]] = None
    message: Optional[str] = None
    enabled: Optional[bool] = None
    standard_version_id: Optional[uuid.UUID] = None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: str
    pattern: str
    replacement: str
    severity: str
    message: str
    enabled: bool
    standard_version_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class RuleSuggestIn(BaseModel):
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    standard_version_id: Optional[uuid.UUID] = None


class RuleSuggestionItem(BaseModel):
    name: str
    kind: RuleKind
    pattern: str
    replacement: str = ""
    severity: Literal["info", "warning", "error"] = "warning"
    message: str = ""
    standard_version_id: Optional[uuid.UUID] = None


class RuleSuggestOut(BaseModel):
    suggestions: list[RuleSuggestionItem]
    documents_analyzed: int


# ----- Import checklist Excel -------------------------------------------------


class SheetInfo(BaseModel):
    name: str
    header_row: int = 0  # ligne d'en-tete detectee (0-based)
    rows: list[list[str]] = Field(default_factory=list)  # grille d'apercu


class SheetInspectOut(BaseModel):
    sheets: list[SheetInfo] = Field(default_factory=list)


class RuleImportResult(BaseModel):
    mode: str = "replace"
    imported: int = 0
    replaced_count: int = 0
    by_kind: dict[str, int] = Field(default_factory=dict)
    skipped_manual: int = 0
    skipped: list[str] = Field(default_factory=list)
    rules: list["CompiledRuleSummary"] = Field(default_factory=list)


class CompiledRuleSummary(BaseModel):
    id: str
    topic: str
    severity: Literal["info", "warning", "error"] = "warning"
    execution: Literal["deterministic", "semantic", "manual", "unsupported"]
    active: bool
    source: Literal["standard_rule", "user_checklist"]
    standard_id: Optional[uuid.UUID] = None
    standard_version_id: Optional[uuid.UUID] = None
    origin_ref: Optional[str] = None
    semantic_instruction: Optional[str] = None
    manual_instruction: Optional[str] = None
    compilation_error: Optional[str] = None
    detail: Optional[str] = None


class CompiledRulePatchIn(BaseModel):
    active: bool


class ClientCatalogOut(BaseModel):
    code: str
    version: str
    standard_version_id: uuid.UUID


class ClientConfigOut(BaseModel):
    client_code: str
    label: str
    bundle: str
    bundle_version: str
    contract_version: str
    manifest_hash: str
    mapping_hash: str
    bundle_hash: str
    catalogs: list[ClientCatalogOut] = Field(default_factory=list)
    mapping: dict[str, Any] = Field(default_factory=dict)
    ui_options: dict[str, Any] = Field(default_factory=dict)


class ClientRuleOut(BaseModel):
    code: str
    name: str
    description: str
    message: str
    kind: str
    severity: Literal["info", "warning", "error"]
    execution: Literal["deterministic", "semantic", "manual", "unsupported"]
    active: bool
    catalog_code: str
    catalog_version: str
    translations: dict[str, dict[str, str]] = Field(default_factory=dict)


class ClientRulePatchIn(BaseModel):
    active: bool


# =============================================================================
# Standards & versions
# =============================================================================


class StandardVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    standard_id: uuid.UUID
    label: str
    builtin: bool
    created_at: datetime
    updated_at: datetime


class StandardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    label: str
    description: Optional[str] = None
    builtin: bool
    versions: list[StandardVersionOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StandardIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    label: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None


class StandardPatchIn(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = None


class StandardVersionIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=60)
    catalog: list[dict[str, Any]] = Field(default_factory=list)


class CatalogRuleOut(BaseModel):
    """A single built-in rule entry from `StandardVersion.catalog_json`."""

    code: str
    title: str
    description: str
    description_en: Optional[str] = None
    kind: str
    severity: str = "warning"
    pattern: str = ""
    replacement: str = ""
    message: str = ""
    message_en: Optional[str] = None
    example_invalid: str = ""
    example_valid: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class StandardVersionDetailOut(StandardVersionOut):
    catalog: list[CatalogRuleOut] = Field(default_factory=list)
    custom_rules: list[RuleOut] = Field(default_factory=list)
    disabled_rule_codes: list[str] = Field(default_factory=list)


class CatalogRulePatchIn(BaseModel):
    """Expert edit on a single catalog entry. Every field is optional;
    only the provided keys are mutated. `code` is the URL parameter and
    cannot be renamed (would break the toggle state and analyse traces)."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = None
    description_en: Optional[str] = None
    severity: Optional[Literal["info", "warning", "error"]] = None
    kind: Optional[RuleKind] = None
    pattern: Optional[str] = None
    replacement: Optional[str] = None
    message: Optional[str] = None
    message_en: Optional[str] = None
    example_invalid: Optional[str] = None
    example_valid: Optional[str] = None


# =============================================================================
# Settings (Mistral)
# =============================================================================


class MistralSettingsIn(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.mistral.ai"
    chat_model: str = "mistral-small-latest"
    vision_model: str = "mistral-medium-3-5"
    vision_enabled: Optional[bool] = None
    llm_enabled: Optional[bool] = None
    checklist_ai_scan: Optional[bool] = None


class MistralSettingsOut(BaseModel):
    api_key_set: bool
    api_key_preview: str = ""
    base_url: str
    chat_model: str
    vision_model: str = "mistral-medium-3-5"
    vision_enabled: bool = False
    llm_enabled: bool = True
    llm_tested: bool = False
    checklist_ai_scan: bool = False


class TestConnectionOut(BaseModel):
    ok: bool
    message: str
    models: list[str] = []


# =============================================================================
# History
# =============================================================================


class EditHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    suggestion_id: Optional[uuid.UUID]
    version_before: int
    version_after: int
    snapshot_path: str
    diff_summary: dict[str, Any]
    applied_at: datetime
    rolled_back: bool

    @field_validator("diff_summary", mode="before")
    @classmethod
    def _parse_diff(cls, v: object) -> object:
        if isinstance(v, str):
            try:
                return json.loads(v or "{}")
            except json.JSONDecodeError:
                return {}
        return v
