from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OcrProviderOut(BaseModel):
    id: str
    label: str
    available: bool
    external: bool
    reason: str | None


class PreparationPageOut(BaseModel):
    page: int
    native_text_chars: int
    native_text_usable: bool
    needs_ocr: bool


class PreparationStateOut(BaseModel):
    document_id: str
    source_filename: str | None
    source_sha256: str | None
    page_count: int
    selected_provider: str | None
    pages: list[PreparationPageOut] = Field(default_factory=list)
    ocr_results_available: list[dict[str, Any]] = Field(default_factory=list)
    validated_pages: list[int] = Field(default_factory=list)
    checklist_rule_count: int
    checklist_imported_rule_count: int = 0
    preparation_rule_count: int = 0
    checklist_source_filename: str | None
    page_decisions: list[dict[str, Any]] = Field(default_factory=list)
    preparation_mapping: dict[str, Any] = Field(default_factory=dict)
    page_classification: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    page_type_options: list[str] = Field(default_factory=list)
    missing_page_types: list[list[str]] = Field(default_factory=list)
    absent_page_types: list[list[str]] = Field(default_factory=list)
    skipped_rules: list[dict[str, Any]] = Field(default_factory=list)


class OcrResultOut(BaseModel):
    page: int
    provider: str
    text: str
    boxes: list[dict[str, Any]] = Field(default_factory=list)
    elapsed_ms: int


class PreparationPageTextOut(BaseModel):
    page: int
    text: str


class OcrDocumentRunOut(BaseModel):
    provider: Literal["mistral"]
    page_count: int
    elapsed_ms: int


class OcrDocumentValidationOut(BaseModel):
    provider: Literal["mistral"]
    validated_pages: list[int]


class OcrRunIn(BaseModel):
    provider: Literal["mistral", "paddle", "indra"]


class ProviderPatchIn(BaseModel):
    provider: Literal["mistral", "paddle", "indra"]


class ReadabilityPatchIn(BaseModel):
    needs_ocr: bool


class OcrValidationPatchIn(BaseModel):
    provider: Literal["mistral", "paddle", "indra"]
    validated: bool


class PageDecisionPatchIn(BaseModel):
    is_modified: bool


class PageClassificationPatchIn(BaseModel):
    page_type: str | None = Field(default=None, max_length=60)
    document_page: str | None = Field(default=None, max_length=40)


class AbsentPageTypesPatchIn(BaseModel):
    page_types: list[str] = Field(min_length=1, max_length=10)
    absent: bool


class PreparationPageTitlesPatchIn(BaseModel):
    titles: list[str] = Field(max_length=200)


class PreparationMappingPatchIn(BaseModel):
    mapping: dict[str, Any] = Field(default_factory=dict)


class PageDecisionOut(BaseModel):
    page: int
    page_type: str | None
    is_modified: bool | None
    decision_status: Literal["selected", "not_selected", "needs_review", "no_applicable_rule"]
    rule_results: list[dict[str, Any]] = Field(default_factory=list)
    failures: list[dict[str, Any]] = Field(default_factory=list)
    review_reasons: list[dict[str, Any]] = Field(default_factory=list)
    toc_page: int | None = None
    toc_bbox: list[float] | None = None


class ChecklistImportOut(BaseModel):
    client_code: str
    source_filename: str
    imported: int
    unsupported: int
    content_sha256: str


class OcrProviderName(BaseModel):
    provider: Literal["mistral", "paddle", "indra"]
