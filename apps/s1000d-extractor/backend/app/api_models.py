"""Public response contracts for wizard, validation and source resources."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class CandidateOut(OutputModel):
    element: str
    score: float | None = None
    rationale: str = ""


class NodeRefOut(OutputModel):
    kind: str
    target: str | None = None
    target_kind: str | None = None
    text: str | None = None


class TreeNodeOut(OutputModel):
    id: str
    kind: str
    text: str = ""
    context: str = "unknown"
    confidence: float | None = 1.0
    candidates: list[CandidateOut] = Field(default_factory=list)
    children: list[TreeNodeOut] = Field(default_factory=list)
    level: int | None = None
    page: int | None = None
    zone: str = "body"
    table_header: list[str] | None = None
    icn: str | None = None
    refs: list[NodeRefOut] | None = None


class DmValidationViolationOut(OutputModel):
    severity: Literal["error", "warning", "info"]
    rule: str
    message: str
    path: str = "/"
    line: int | None = None
    column: int | None = None
    brex_rule_id: str | None = None
    brex_severity_level: str | None = None


class DmValidationResultOut(OutputModel):
    filename: str
    dmc: str
    issue: str | None
    schema_name: str | None = Field(alias="schema")
    status: Literal["valid", "invalid", "needs_issue", "unverifiable"]
    error_count: int
    violations: list[DmValidationViolationOut]
    message: str | None = None


class DmValidationBatchOut(OutputModel):
    results: list[DmValidationResultOut]


class GeneratedDmValidationResultOut(DmValidationResultOut):
    dm_id: str


class WizardValidationOut(OutputModel):
    results: list[GeneratedDmValidationResultOut]


class PreviewSnippetOut(OutputModel):
    text: str
    page: int | None
    kind: str
    zone: str | None = None


class DmPreviewOut(OutputModel):
    head: list[PreviewSnippetOut]
    tail: list[PreviewSnippetOut]
    total: int


class WizardDmOut(OutputModel):
    dm_id: str
    title: str
    dm_type: str
    node_count: int
    dmc: str = ""
    is_orphan: bool = False
    preview: DmPreviewOut | None = None
    tree: TreeNodeOut | None = None
    violation_count: int = 0
    has_xml: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    xsd_valid: bool | None = None
    xsd_violations: list[DmValidationViolationOut] = Field(default_factory=list)
    brex_violations: list[DmValidationViolationOut] = Field(default_factory=list)
    cir_unresolved: list[str] = Field(default_factory=list)


class WizardResourcesOut(OutputModel):
    dmrl_count: int
    has_cir: bool
    has_brex_rules: bool
    has_dm_header: bool
    errors: list[str] = Field(default_factory=list)


class DmrlRowOut(OutputModel):
    index: int
    arbo: str
    dmc: str
    title: str
    dm_type: str
    dmrl_type: str = ""
    info_code: str = ""
    info_code_schema: str = ""
    info_code_dm_type: str = ""
    type_conflict: bool = False
    type_issue: Literal["", "missing_info_code", "unmapped_info_code", "unsupported_schema"] = ""
    icn: str = ""
    is_pm_title: bool = False
    matched: bool
    match_rank: Literal["", "exact", "prefix", "contains"]
    page: int | None
    matched_text: str


class ReaderPositionOut(OutputModel):
    page: int
    scroll_top: float
    selected_id: str | None


class ReviewPassageOut(OutputModel):
    id: str
    node_id: str
    row: int | None
    start: int
    end: int
    source_text: str
    text: str
    page: int | None
    kind: str
    role: str = "content"
    phase: str = "unknown"
    suggested: str
    rule: str
    decision: str | None


class ProcedureReviewOut(OutputModel):
    fingerprint: str
    rules_revision: int = 0
    status: Literal["pending", "reviewed", "skipped", "stale"]
    partial: bool = False
    passages: list[ReviewPassageOut]
    position: ReaderPositionOut
    saved_at: str | None


class PreliminaryStateOut(OutputModel):
    revision: int
    active_dm_id: str | None
    source_format: str
    source_changed: bool
    reviews: dict[str, ProcedureReviewOut]


class WizardStateOut(OutputModel):
    step: Literal["dmrl", "split", "type", "structure", "preliminary", "generate"]
    split_level: str
    dms: list[WizardDmOut]
    dmrl_dm_count: int = 0
    steps: list[Literal["dmrl", "split", "type", "structure", "preliminary", "generate"]] = Field(
        default_factory=list
    )
    can_undo: bool = False
    has_brex_profile: bool = False
    illustration_errors: int = 0
    resources: WizardResourcesOut | None = None
    dmrl: list[DmrlRowOut] | None = None
    preliminary: PreliminaryStateOut | None = None


class ResourceUploadOut(OutputModel):
    kind: Literal["dmrl", "cir", "brex_rules", "dm_header"]
    count: int


class DmrlEntryOut(OutputModel):
    arbo: str
    dmc: str
    title: str
    dm_type: str
    icn: str


class PdfCutCandidateOut(OutputModel):
    page: int
    score: float
    reasons: list[str]
    preview: str


class PdfCutDetectionOut(OutputModel):
    validation_required: bool
    selected_page: int | None
    selected_end_page: int | None
    default_start_page: int
    total_pages: int
    dmrl_titles: list[str]
    candidates: list[PdfCutCandidateOut]


class PdfCutConfirmedOut(OutputModel):
    page: int
    start_page: int
    end_page: int
    page_count: int
    status: str


class SourcePageOut(OutputModel):
    page: int
    width: float
    height: float


class PageAnchorsOut(OutputModel):
    width: float
    height: float
    anchors: dict[str, list[tuple[float, float, float, float]]]


class LinkDmrlOut(OutputModel):
    doc_id: str
    mode: str
    links_created: int


class RestoredVersionOut(OutputModel):
    doc_id: str
    original_version_id: str
    restored_version_id: str
    dm_code: str
    created_at: str
