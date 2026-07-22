"""Pydantic v2 I/O schemas — Vague A (projets, fichiers, anomalies, settings, analyse)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Project
# =============================================================================


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)
    vision_enabled: bool = False


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)
    vision_enabled: Optional[bool] = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    vision_enabled: bool
    created_at: datetime


# =============================================================================
# Files
# =============================================================================


class FileVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    sha256: str
    size: int
    uploaded_at: datetime


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    current_name: str
    mime_type: str
    created_at: datetime
    versions: list[FileVersionOut] = []


class UploadResultOut(BaseModel):
    uploaded: list[dict[str, Any]]


class ReferenceColumnDef(BaseModel):
    """Une colonne du registre de référence d'un projet."""
    name: str
    sheet: str = ""
    column: str = ""
    builtin: bool = False


class ReferenceOut(BaseModel):
    """Référentiel v4 : classeur Excel unique (onglets ATM / BASL / LCC)
    contre lequel les checks cross-checkent le livrable FTM."""
    path: Optional[str] = None
    sheets: list[str] = Field(default_factory=list)
    # Registre des colonnes de référence (builtin + colonnes ajoutées).
    columns: list[ReferenceColumnDef] = Field(default_factory=list)
    # Ligne d'en-tête choisie par onglet (1-based) — {onglet: ligne}. Vide =
    # détection auto. Sert à lire les bons libellés de colonnes dans le mapping.
    header_rows: dict[str, int] = Field(default_factory=dict)


class SheetColumnOut(BaseModel):
    """Colonne d'un onglet Excel — alimente les menus déroulants « Colonne »."""
    letter: str
    header: str = ""


class SheetPreviewOut(BaseModel):
    """Aperçu d'un onglet pour désigner la ligne d'en-tête dans le mapping."""
    # Indice (1-based) que la détection auto choisirait ; 0 si onglet vide.
    header_row_detected: int = 0
    rows: list[list[str]] = Field(default_factory=list)


class ReferenceColumnIn(BaseModel):
    """Entrée du mapping envoyée par l'UI (le flag builtin est recalculé serveur)."""
    name: str
    sheet: str = ""
    column: str = ""


class ReferenceMappingIn(BaseModel):
    columns: list[ReferenceColumnIn] = Field(default_factory=list)
    # Ligne d'en-tête choisie par onglet (1-based). Onglet absent = détection auto.
    header_rows: dict[str, int] = Field(default_factory=dict)


# =============================================================================
# Anomalies
# =============================================================================


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    file_version_id: Optional[uuid.UUID]
    type: str
    # Categorie metier (Sujet de la regle checklist) — dimension de regroupement KPI.
    category: str = ""
    severity: str
    confidence: str = "elevee"
    message: str
    suggestion: str
    # Motif de rejet / commentaire du relecteur (vide par défaut).
    feedback: str = ""
    # i18n : si `message_key` est non-null, le front résout via t(key, params)
    # et utilise `message` (FR) en fallback. `*_params` est sérialisé en JSON
    # string côté DB ; le schema le restitue tel quel.
    message_key: Optional[str] = None
    message_params_json: Optional[str] = None
    suggestion_key: Optional[str] = None
    suggestion_params_json: Optional[str] = None
    location: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]


class AnomalyStatusIn(BaseModel):
    status: str  # open | acknowledged | fixed | rejected
    # Motif libre (facultatif) — surtout au rejet. None = ne pas modifier.
    feedback: Optional[str] = None


class AnomalyBulkStatusIn(BaseModel):
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    status: str  # open | acknowledged | fixed | rejected
    feedback: Optional[str] = None


class AnomalyBulkStatusOut(BaseModel):
    updated: int
    status: str


# =============================================================================
# Analysis runs
# =============================================================================


class AnalysisRunIn(BaseModel):
    """Corps optionnel du déclenchement d'analyse. `file_ids` restreint
    l'analyse à un échantillon de fichiers du projet (réanalyse ciblée pour
    itérer sur la checklist). Vide / absent = tout le projet."""

    file_ids: Optional[list[uuid.UUID]] = None


class AnalysisRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    summary: str


# =============================================================================
# Mistral settings
# =============================================================================


class MistralSettingsIn(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.mistral.ai"
    chat_model: str = "mistral-small-latest"
    embed_model: str = "mistral-embed"
    vision_model: str = "pixtral-large-latest"
    # Interrupteur global IA. None = ne pas modifier (toggle indépendant des
    # autres champs Mistral) ; True/False = activer/désactiver.
    llm_enabled: Optional[bool] = None


class MistralSettingsOut(BaseModel):
    api_key_set: bool
    api_key_preview: str = ""
    base_url: str
    chat_model: str
    embed_model: str
    vision_model: str
    llm_enabled: bool
    llm_tested: bool = False


class TestConnectionOut(BaseModel):
    ok: bool
    message: str
    models: list[str] = []


# =============================================================================
# Chat
# =============================================================================


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    scope_project_ids: list[uuid.UUID] = Field(default_factory=list)
    title: str
    created_at: datetime

    @field_validator("scope_project_ids", mode="before")
    @classmethod
    def _parse_scope(cls, v: object) -> object:
        if isinstance(v, str):
            try:
                return [uuid.UUID(s) for s in json.loads(v or "[]")]
            except (json.JSONDecodeError, ValueError):
                return []
        return v


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    citations: str
    created_at: datetime


class ChatAskIn(BaseModel):
    session_id: Optional[uuid.UUID] = None
    project_ids: list[uuid.UUID] = Field(default_factory=list)  # vide = tous les projets
    question: str = Field(..., min_length=1, max_length=4000)
    lang: str = "fr"


# =============================================================================
# KPIs
# =============================================================================


class KpiOut(BaseModel):
    open_anomalies: int
    anomalies_by_severity: dict[str, int]
    anomalies_by_type: dict[str, int]
    # Repartition par categorie metier (Sujet des regles checklist) — dimension
    # de regroupement en mode checklist-only.
    anomalies_by_category: dict[str, int] = Field(default_factory=dict)
    # Repartition des anomalies sur le workflow d'etat (open / acknowledged /
    # fixed / rejected). dmc_missing exclu (couverture referentiel, pas un ticket).
    anomalies_by_status: dict[str, int]
    # Taux de resolution = fixed / total des anomalies qualite, en pourcentage.
    resolution_rate: float
    # Repartition des anomalies ouvertes par niveau de confiance IA
    # (elevee / moyenne / faible).
    anomalies_by_confidence: dict[str, int]
    anomalies_over_time: list[dict[str, Any]]
    top_files: list[dict[str, Any]]
    top_rules: list[dict[str, Any]]
    avg_age_days: float
    avg_resolution_days: float
    files_total: int
    files_with_anomalies: int


# =============================================================================
# Import checklist (regles personnalisees en masse)
# =============================================================================


class SheetInfo(BaseModel):
    """Apercu d'un onglet Excel : ligne d'en-tete detectee + grille rectangulaire."""

    name: str
    header_row: int = 0
    rows: list[list[str]]


class SheetInspectOut(BaseModel):
    sheets: list[SheetInfo]


class ChecklistImportResult(BaseModel):
    """Bilan d'un import de checklist dans les regles personnalisees."""

    mode: str = "replace"
    imported: int = 0
    created: int = 0
    updated: int = 0
    replaced_count: int = 0
    skipped: list[str] = Field(default_factory=list)
    # Total de regles en attente de validation apres l'import (file de validation).
    pending: int = 0
