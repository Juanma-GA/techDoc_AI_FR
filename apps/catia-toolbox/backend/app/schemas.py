"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _parse_json_dict(v: object) -> object:
    """Parse une colonne Text JSON ('{...}') en dict pour les response models."""
    if isinstance(v, str):
        try:
            return json.loads(v or "{}")
        except json.JSONDecodeError:
            return {}
    return v


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
    onedrive_input_root: Optional[str] = None
    onedrive_output_root: Optional[str] = None


class SettingsOut(BaseModel):
    api_key_set: bool
    base_url: str
    chat_model: str
    embed_model: str
    llm_enabled: bool
    llm_tested: bool = False
    onedrive_input_root: str = ""
    onedrive_output_root: str = ""


# ----- Navigation OneDrive (browse) -----------------------------------------


class BrowseRootsOut(BaseModel):
    """Racines OneDrive configurees + candidats auto-detectes."""

    input: str = ""
    output: str = ""
    detected: list[str] = Field(default_factory=list)


class BrowseListIn(BaseModel):
    scope: str = Field(default="input")  # input | output
    path: str = Field(default="")  # vide => racine du scope


class BrowseEntryOut(BaseModel):
    name: str
    path: str
    kind: str = "file"  # file | folder
    ext: str = ""
    size: int = 0
    mtime: Optional[datetime] = None
    rel: str = ""  # chemin relatif a la racine listee (vue recursive)


class BrowseListOut(BaseModel):
    scope: str
    root: str
    path: str
    entries: list[BrowseEntryOut] = Field(default_factory=list)


# ----- Import par selection (fichiers ET dossiers) --------------------------


class SelectImportIn(BaseModel):
    scope: str = Field(default="input")  # input | output
    paths: list[str] = Field(..., min_length=1)
    max_nodes: int = Field(default=20000, ge=1, le=200000)


# ----- Ecriture des livrables dans le dossier de sortie ---------------------


class ExportSaveIn(BaseModel):
    filename: str = Field(..., min_length=1)
    kind: str = Field(default="csv")  # csv | bat | sh
    status: str = Field(default="accepted")


class ExportSaveOut(BaseModel):
    path: str
    bytes_written: int


class TestConnectionOut(BaseModel):
    ok: bool
    models: list[str] = Field(default_factory=list)
    error: Optional[str] = None


# ----- Admin (stats + reset) ------------------------------------------------


class AdminStatsOut(BaseModel):
    """Compteurs sommaires affiches dans l'onglet Donnees du preview."""

    imports: int = 0
    nodes: int = 0
    runs: int = 0
    suggestions: int = 0
    diffs: int = 0
    checks: int = 0
    conversions: int = 0
    replacements: int = 0
    colorizations: int = 0
    nomenclatures: int = 0
    smgxml_runs: int = 0
    qc_checklists: int = 0
    total_size_bytes: int = 0


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]


# ----- Imports (scan + listing) ---------------------------------------------


class ScanIn(BaseModel):
    path: str = Field(..., min_length=1)
    max_nodes: int = Field(default=20000, ge=1, le=200000)


class MetricsOut(BaseModel):
    """Vue typee des metriques (tolerante : champs supplementaires ignores)."""

    model_config = ConfigDict(extra="allow")

    node_count: int = 0
    file_count: int = 0
    folder_count: int = 0
    max_depth: int = 0
    avg_depth: float = 0.0
    max_fanout: int = 0


class ImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_mode: str
    root_label: str
    source_ref: str
    node_count: int
    created_at: datetime
    metrics: dict = Field(default_factory=dict)


class TreeNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rel_path: str
    name: str
    ext: str
    kind: str
    depth: int
    size: int
    mtime: Optional[datetime] = None
    children: list["TreeNodeOut"] = Field(default_factory=list)


class TreeOut(BaseModel):
    import_id: uuid.UUID
    root_label: str
    node_count: int
    metrics: dict = Field(default_factory=dict)
    nodes: list[TreeNodeOut] = Field(default_factory=list)


# ----- Optimisation ---------------------------------------------------------


class OptimizeIn(BaseModel):
    target_max_depth: int = Field(default=5, ge=1, le=20)
    strategy: str = Field(default="by_type")
    use_llm: bool = True


class OptimizationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    import_id: uuid.UUID
    status: str
    summary: dict = Field(default_factory=dict)
    started_at: datetime
    finished_at: Optional[datetime] = None


# ----- Suggestions ----------------------------------------------------------


class SuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    old_path: str
    new_path: str
    action: str
    rationale: str
    confidence: str
    source: str
    status: str
    created_at: datetime


class SuggestionStatusIn(BaseModel):
    status: str


class SuggestionBulkStatusIn(BaseModel):
    ids: list[uuid.UUID] = Field(default_factory=list)
    status: str


class SuggestionBulkStatusOut(BaseModel):
    updated: int
    status: str


# ----- Module Comparaison ---------------------------------------------------


class DiffIn(BaseModel):
    base_import_id: uuid.UUID
    other_import_id: uuid.UUID


class DiffEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rel_path: str
    change_type: str
    detail: str


class DiffRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    base_import_id: uuid.UUID
    other_import_id: uuid.UUID
    status: str
    summary: dict = Field(default_factory=dict)
    created_at: datetime

    _v_summary = field_validator("summary", mode="before")(_parse_json_dict)


# ----- Module Verifications -------------------------------------------------


class CheckIn(BaseModel):
    rules: Optional[list[str]] = None
    max_depth: int = 6
    naming_style: str = "kebab"
    forbidden_extensions: list[str] = Field(default_factory=lambda: ["tmp", "bak", "old"])


class CheckResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule: str
    severity: str
    rel_path: str
    message: str


class CheckRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    import_id: uuid.UUID
    status: str
    summary: dict = Field(default_factory=dict)
    created_at: datetime

    _v_summary = field_validator("summary", mode="before")(_parse_json_dict)


# ----- Module Conversion ----------------------------------------------------


class ConversionIn(BaseModel):
    target_dir: str = "composer"
    target_ext: str = "smg"


class ConversionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_path: str
    target_path: str
    source_ext: str
    status: str


class ConversionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    import_id: uuid.UUID
    status: str
    summary: dict = Field(default_factory=dict)
    created_at: datetime

    _v_summary = field_validator("summary", mode="before")(_parse_json_dict)


# ----- Module Remplacement --------------------------------------------------


class ReplacementItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    occurrence_path: str
    old_ref: str
    new_ref: str
    status: str


class ReplacementRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    import_id: uuid.UUID
    status: str
    summary: dict = Field(default_factory=dict)
    created_at: datetime

    _v_summary = field_validator("summary", mode="before")(_parse_json_dict)


class StatusIn(BaseModel):
    status: str


class ReplacementFromSourceIn(BaseModel):
    scope: str = Field(default="input")
    path: str = Field(..., min_length=1)


# ----- Module Colorisation --------------------------------------------------


class ColorizationIn(BaseModel):
    strategy: str = "by_type"  # by_change | by_type | by_depth
    diff_run_id: Optional[uuid.UUID] = None  # requis si strategy == by_change


class ColorizationItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rel_path: str
    color_r: int
    color_g: int
    color_b: int
    reason: str


class ColorizationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    import_id: uuid.UUID
    diff_run_id: Optional[uuid.UUID] = None
    strategy: str
    status: str
    summary: dict = Field(default_factory=dict)
    created_at: datetime

    _v_summary = field_validator("summary", mode="before")(_parse_json_dict)


# ----- Etape 1 : Identification (nomenclature .xlsm + DE .zip) ---------------


class NomenclatureMapping(BaseModel):
    """Mapping manuel : ligne d'en-tete (1-based) + index de colonne (0-based)."""

    header_row: int = Field(..., ge=1)
    catpart: int = Field(..., ge=0)
    designation: Optional[int] = Field(default=None, ge=0)
    sin: Optional[int] = Field(default=None, ge=0)
    version: Optional[int] = Field(default=None, ge=0)
    to_treat: Optional[int] = Field(default=None, ge=0)
    color: Optional[int] = Field(default=None, ge=0)


class NomenclatureParseIn(BaseModel):
    scope: str = Field(default="input")
    path: str = Field(..., min_length=1)
    sheet: Optional[str] = None
    mapping: Optional[NomenclatureMapping] = None


class NomenclaturePreviewIn(BaseModel):
    scope: str = Field(default="input")
    path: str = Field(..., min_length=1)
    sheet: Optional[str] = None
    rows: int = Field(default=15, ge=1, le=100)


class NomenclaturePreviewOut(BaseModel):
    sheets: list[str] = Field(default_factory=list)
    sheet: str = ""
    header_row_detected: int = 0
    columns_detected: list[str] = Field(default_factory=list)
    columns_map: dict[str, int] = Field(default_factory=dict)
    rows: list[list[str]] = Field(default_factory=list)


class NomenclatureItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    catpart: str
    designation: str
    sin: str
    version: str
    to_treat: bool
    mono_color: bool
    color_r: int
    color_g: int
    color_b: int
    source_row: int


class NomenclatureRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_ref: str
    sheet: str
    status: str
    summary: dict = Field(default_factory=dict)
    created_at: datetime

    _v_summary = field_validator("summary", mode="before")(_parse_json_dict)


class ZipEntryOut(BaseModel):
    name: str
    size: int = 0
    is_dir: bool = False


class ZipListOut(BaseModel):
    path: str
    count: int
    entries: list[ZipEntryOut] = Field(default_factory=list)


# ----- Etapes 3 & 4 : SMGXML ------------------------------------------------


class SmgxmlInspectIn(BaseModel):
    scope: str = Field(default="input")
    path: str = Field(..., min_length=1)


class SmgxmlActorOut(BaseModel):
    name: str
    tag: str = ""
    color: str = ""


class SmgxmlRecolorIn(BaseModel):
    scope: str = Field(default="input")
    path: str = Field(..., min_length=1)
    nomenclature_run_id: uuid.UUID  # source des SIN mono-couleur + couleurs
    match_by: str = Field(default="sin")  # sin | catpart
    apply: bool = False  # False = dry-run (rien ecrit)


class RenamePair(BaseModel):
    old: str = Field(..., min_length=1)
    new: str = Field(..., min_length=1)


class SmgxmlRenameIn(BaseModel):
    scope: str = Field(default="input")
    path: str = Field(..., min_length=1)
    mapping: list[RenamePair] = Field(..., min_length=1)
    apply: bool = False


class SmgxmlChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target: str
    change_type: str
    old_value: str
    new_value: str


class SmgxmlRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_ref: str
    operation: str
    status: str
    applied: bool
    backup_path: str
    output_path: str
    summary: dict = Field(default_factory=dict)
    created_at: datetime

    _v_summary = field_validator("summary", mode="before")(_parse_json_dict)


# ----- Etape 5 : Controle Qualite (checklist) -------------------------------


class QcItemIn(BaseModel):
    label: str = Field(..., min_length=1)
    category: str = ""


class QcChecklistCreateIn(BaseModel):
    title: str = Field(default="Controle qualite")
    template: Optional[str] = None  # "assembly" | None -> items par defaut
    items: list[QcItemIn] = Field(default_factory=list)


class QcItemUpdateIn(BaseModel):
    status: Optional[str] = None  # pending | ok | ko | na
    comment: Optional[str] = None


class QcItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    category: str
    status: str
    comment: str
    position: int


class QcChecklistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: str
    created_at: datetime
    items: list[QcItemOut] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
