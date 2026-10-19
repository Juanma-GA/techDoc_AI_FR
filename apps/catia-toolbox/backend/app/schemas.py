"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Literal, Optional

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
    composer_license_server: Optional[str] = None
    composer_converter_path: Optional[str] = None
    composer_settings_path: Optional[str] = None


class SettingsOut(BaseModel):
    api_key_set: bool
    base_url: str
    chat_model: str
    embed_model: str
    llm_enabled: bool
    llm_tested: bool = False
    onedrive_input_root: str = ""
    onedrive_output_root: str = ""
    composer_license_server: str = ""
    composer_converter_path: str = ""
    composer_settings_path: str = ""


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


class LocalUploadFileOut(BaseModel):
    path: str
    rel: str
    size: int


class LocalUploadOut(BaseModel):
    root: str
    files: list[LocalUploadFileOut] = Field(default_factory=list)


class BrowsePreviewIn(BaseModel):
    scope: str = Field(default="input")  # input | output
    path: str = Field(..., min_length=1)
    sheet: Optional[str] = None  # onglet a previsualiser (defaut : le premier)
    rows: int = Field(default=15, ge=1, le=100)  # nombre de lignes a afficher


class BrowsePreviewOut(BaseModel):
    """Apercu generique d'un classeur Excel : onglets + premieres lignes.
    Contrairement a `NomenclaturePreviewOut`, sans le mapping metier."""

    sheets: list[str] = Field(default_factory=list)
    sheet: str = ""
    rows: list[list[str]] = Field(default_factory=list)


# ----- Import par selection (fichiers ET dossiers) --------------------------


class SelectImportIn(BaseModel):
    scope: str = Field(default="input")  # input | output
    paths: list[str] = Field(..., min_length=1)
    max_nodes: int = Field(default=20000, ge=1, le=200000)


class ZipImportIn(BaseModel):
    """Import d'un dossier entier livre en .zip (metadonnees seules)."""

    scope: str = Field(default="input")  # input | output
    path: str = Field(..., min_length=1)  # chemin du .zip sous la racine
    max_nodes: int = Field(default=20000, ge=1, le=200000)


# ----- Ecriture des livrables dans le dossier de sortie ---------------------


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
    # Vide => dossier de sortie auto '<NomDossierInput>_Converti' (a plat).
    target_dir: str = ""
    target_ext: str = "smgxml"


class ConversionItemStatusIn(BaseModel):
    # accepted (retenu) | rejected (deselectionne).
    status: str = Field(..., pattern="^(accepted|rejected|pending)$")


class ConversionBulkStatusIn(BaseModel):
    item_ids: list[uuid.UUID] = Field(..., min_length=1)
    status: str = Field(..., pattern="^(accepted|rejected|pending)$")


class ConversionExecIn(BaseModel):
    # dry_run=True (defaut) : lance le script en DRY_RUN (aucune action Composer).
    # dry_run=False : execution reelle -> exige confirm=True (garde-fou).
    dry_run: bool = True
    confirm: bool = False


class ConversionExecOut(BaseModel):
    dry_run: bool
    returncode: int
    stdout: str = ""
    stderr: str = ""
    base: str = ""  # dossier racine utilise pour resoudre les chemins
    converted: int = 0
    failed: int = 0


class ComposerConverterStatusOut(BaseModel):
    available: bool
    executable: str = ""
    settings_file: str = ""
    version: str = ""
    message: str


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


class MonoBodyColorizationIn(BaseModel):
    scope: str = Field(default="input")
    pieces_root: str = Field(..., min_length=1)
    profiles_root: str = Field(..., min_length=1)
    nomenclature_run_id: uuid.UUID
    apply: bool = False


class MonoBodyColorizationItemOut(BaseModel):
    old_pn: str = ""
    texture_ref: str = ""
    profile_path: str = ""
    path: str = ""
    status: str = ""
    actors_total: int = 0
    actors_changed: int = 0
    message: str = ""
    applied: bool = False


class MonoBodyColorizationOut(BaseModel):
    items: list[MonoBodyColorizationItemOut] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


# ----- Etape 1 : Identification (nomenclature .xlsm + DE .zip) ---------------


class NomenclatureMapping(BaseModel):
    """Mapping manuel : ligne d'en-tete (1-based) + index de colonne (0-based)."""

    header_row: int = Field(..., ge=1)
    # Identite = au moins une colonne parmi catpart / sin / old_pn / new_pn
    # (verifie cote parser). Aucune n'est individuellement obligatoire.
    catpart: Optional[int] = Field(default=None, ge=0)
    designation: Optional[int] = Field(default=None, ge=0)
    sin: Optional[int] = Field(default=None, ge=0)
    version: Optional[int] = Field(default=None, ge=0)
    to_treat: Optional[int] = Field(default=None, ge=0)
    optimized: Optional[int] = Field(default=None, ge=0)
    color: Optional[int] = Field(default=None, ge=0)
    old_pn: Optional[int] = Field(default=None, ge=0)
    new_pn: Optional[int] = Field(default=None, ge=0)
    old_rev: Optional[int] = Field(default=None, ge=0)
    new_rev: Optional[int] = Field(default=None, ge=0)
    replaced: Optional[int] = Field(default=None, ge=0)
    color_ref: Optional[int] = Field(default=None, ge=0)
    materials: Optional[int] = Field(default=None, ge=0)


class MonoCorpsIn(BaseModel):
    """Etape Mono-Corps : onglet Materiaux (identite + n colonnes slots).

    Analyse autonome (le contenu est renvoye pour affichage). Si `run_id` est
    fourni, le drapeau mono_body est aussi applique aux pieces de ce run.
    """

    scope: str = Field(default="input")
    path: str = Field(..., min_length=1)
    sheet: Optional[str] = None
    header_row: int = Field(..., ge=1)
    # Champ d'identite (catpart | sin | old_pn | new_pn) reliant la ligne slots
    # a une piece, et l'index (0-based) de la colonne d'identite dans l'onglet.
    identity_field: str = Field(..., min_length=1)
    identity_col: int = Field(..., ge=0)
    # Colonnes slots (0-based). Vide/omis => de `first_slot_col` a la fin.
    slot_cols: list[int] = Field(default_factory=list)
    # 1re colonne Slot (0-based) : comparee a toutes les colonnes suivantes.
    first_slot_col: Optional[int] = Field(default=None, ge=0)
    # Optionnel : run de nomenclature auquel appliquer mono_body.
    run_id: Optional[uuid.UUID] = None


class MonoCorpsItemOut(BaseModel):
    identity: str = ""
    old_pn: str = ""
    slots: list[str] = Field(default_factory=list)
    mono_body: bool = False
    mono_texture: str = ""


class MonoCorpsResultOut(BaseModel):
    items: list[MonoCorpsItemOut] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


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
    to_treat_value: str
    optimized: bool
    replaced: bool
    old_pn: str
    new_pn: str
    old_rev: str
    new_rev: str
    color_ref: str
    materials: str
    mono_body: bool
    mono_texture: str
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


class NomenclatureCompareIn(BaseModel):
    """Comparaison de deux runs de nomenclature (A = base, B = nouvelle)."""

    base_run_id: uuid.UUID
    other_run_id: uuid.UUID


class SinEntryOut(BaseModel):
    sin: str
    old_pn: str = ""
    old_pn_v2: str = ""
    designation: str = ""


class PnChangeOut(BaseModel):
    sin: str
    old_pn: str = ""
    old_pn_v2: str = ""
    designation: str = ""


class NomenclatureCompareOut(BaseModel):
    base_run_id: uuid.UUID
    other_run_id: uuid.UUID
    added_sin: list[SinEntryOut] = Field(default_factory=list)
    removed_sin: list[SinEntryOut] = Field(default_factory=list)
    changed_pn: list[PnChangeOut] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


class NomenclatureMultiCompareIn(BaseModel):
    """Comparaison ordonnee de 2 a 10 runs de nomenclature."""

    run_ids: list[uuid.UUID] = Field(..., min_length=2, max_length=10)
    mode: Literal["chronology", "reference"] = "chronology"
    reference_run_id: uuid.UUID | None = None


class NomenclatureMatrixCellOut(BaseModel):
    run_id: uuid.UUID
    present: bool
    pn: str = ""
    state: Literal["unchanged", "added", "removed", "changed", "reference"] = "unchanged"


class NomenclatureMatrixRowOut(BaseModel):
    sin: str
    designation: str = ""
    cells: list[NomenclatureMatrixCellOut] = Field(default_factory=list)


class NomenclatureMultiCompareOut(BaseModel):
    mode: Literal["chronology", "reference"]
    run_ids: list[uuid.UUID]
    reference_run_id: Optional[uuid.UUID] = None
    comparisons: list[NomenclatureCompareOut] = Field(default_factory=list)
    matrix: list[NomenclatureMatrixRowOut] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


class ZipEntryOut(BaseModel):
    name: str
    size: int = 0
    is_dir: bool = False


class ZipListOut(BaseModel):
    path: str
    count: int
    entries: list[ZipEntryOut] = Field(default_factory=list)


class ZipImportOut(ImportOut):
    """Import cree depuis un .zip + apercu du contenu (listing unifie)."""

    count: int = 0
    entries: list[ZipEntryOut] = Field(default_factory=list)


class SmgxmlBatchRenameIn(BaseModel):
    """Renommage en masse : racine COMPOSER (sous-dossiers COMP PROD / COMP PART)
    + dossier des pieces NEW converties + run de nomenclature source des paires."""

    scope: str = Field(default="input")
    composer_root: str = Field(..., min_length=1)
    converted_root: str = Field(..., min_length=1)
    nomenclature_run_id: uuid.UUID
    apply: bool = False


class SmgxmlBatchItemOut(BaseModel):
    sin: str = ""
    old_pn: str = ""
    new_pn: str = ""
    old_stem: str = ""
    new_stem: str = ""
    assembly: str = ""
    replacements: int = 0
    archived: list[str] = Field(default_factory=list)
    copied: list[str] = Field(default_factory=list)
    status: str = "ok"
    message: str = ""
    applied: bool = False


class SmgxmlBatchOut(BaseModel):
    items: list[SmgxmlBatchItemOut] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


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


class TreeOptimizationCountIn(BaseModel):
    path: str = Field(..., min_length=1)


class TreeOptimizationCountOut(BaseModel):
    path: str
    files_count: int


class TreeOptimizationIn(BaseModel):
    path: str = Field(..., min_length=1)
    apply: bool = False


class TreeOptimizationFolderPickerIn(BaseModel):
    initial_path: Optional[str] = None
    title: str = Field(default="Select a folder", max_length=120)


class TreeOptimizationFolderPickerOut(BaseModel):
    path: Optional[str] = None


class TreeOptimizationOut(BaseModel):
    path: str
    applied: bool
    files_scanned: int
    files_with_changes: int
    files_modified: int
    removed_elements: int
