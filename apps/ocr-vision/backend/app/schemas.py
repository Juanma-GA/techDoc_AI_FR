"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

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
    vision_model: Optional[str] = None
    llm_enabled: Optional[bool] = None


class SettingsOut(BaseModel):
    api_key_set: bool
    base_url: str
    chat_model: str
    embed_model: str
    vision_model: str
    llm_enabled: bool
    llm_tested: bool = False


class TestConnectionOut(BaseModel):
    ok: bool
    models: list[str] = Field(default_factory=list)
    error: Optional[str] = None


# ----- Admin (stats + reset) ------------------------------------------------


class AdminStatsOut(BaseModel):
    """Compteurs affiches dans l'onglet Donnees."""

    projects: int = 0
    templates: int = 0
    tables: int = 0
    rows: int = 0
    images: int = 0


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]


# ----- Capitalisation : templates / projets / tables / lignes ---------------


ColumnType = Literal["text", "number", "date", "bool"]


class ColumnSpec(BaseModel):
    """Une colonne de table : cle technique, libelle, type, regle d'extraction."""

    key: str = Field(..., min_length=1, max_length=100)
    label: str = ""
    type: ColumnType = "text"
    rule: str = ""


class TemplateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    columns: list[ColumnSpec] = Field(default_factory=list)


class TemplateOut(BaseModel):
    id: str
    name: str
    description: str
    columns: list[ColumnSpec]
    created_at: datetime


class ProjectIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class RenameIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class ProjectOut(BaseModel):
    id: str
    name: str
    created_at: datetime


class ProjectTableIn(BaseModel):
    project_id: str
    template_id: str
    name: Optional[str] = None


class ProjectTableOut(BaseModel):
    id: str
    project_id: str
    template_id: str
    name: str
    columns: list[ColumnSpec]
    row_count: int = 0
    created_at: datetime


class RowOut(BaseModel):
    id: str
    source_filename: str
    values: dict[str, object]
    created_at: datetime


class ExtractOut(BaseModel):
    rows_added: int
    rows: list[RowOut]
    images_added: int = 0
    warning: str = ""


class ImageOut(BaseModel):
    id: str
    source_filename: str
    filename: str
    page: Optional[int] = None
    url: str
    created_at: datetime


class ExportIn(BaseModel):
    project_table_id: str
    target_dir: str = Field(..., min_length=1)
    format: Literal["csv", "xlsx"] = "csv"


class ExportOut(BaseModel):
    path: str
    rows: int
    format: str = "csv"
