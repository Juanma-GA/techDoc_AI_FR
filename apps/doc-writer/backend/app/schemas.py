"""Pydantic v2 I/O schemas — un modèle par body / response."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ----- Health ----------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    llm: str


# ----- Documents -------------------------------------------------------------


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str
    size: int
    sha256: str
    chunk_count: int
    index_error: Optional[str] = None
    kind: str = "source"  # source | template | style
    uploaded_at: datetime


class DocumentContentOut(BaseModel):
    """Texte extrait d'un document (pour visualiser ce que le parsing/OCR a
    produit). `char_count` aide a reperer une extraction vide/partielle."""
    id: uuid.UUID
    filename: str
    kind: str
    char_count: int
    text: str


class ZoneOut(BaseModel):
    id: str
    kind: str          # "placeholder" | "xxx" | "llm"
    slide_index: int
    slide_title: str
    label: str
    location: str
    target: str = ""   # Pour kind="llm" : path encode vers shape/cellule.
    active: bool = True  # False = exclue du remplissage a l'export.
    instruction: str = ""  # Consignes libres pour le LLM de remplissage.
    align: str = ""  # Alignement force : ""=auto|left|center|right|justify.


class ZonesOut(BaseModel):
    zones: list[ZoneOut]
    # Zones supprimees par l'utilisateur (soft-delete). Restaurables via
    # POST /documents/<id>/zones/<zone_id>/restore. Permet d'annuler une
    # suppression accidentelle sans re-analyser tout le template.
    removed: list[ZoneOut] = Field(default_factory=list)
    llm_used: bool = False
    # Zones LLM rejetees par les checks de coherence (cf.
    # pptx_llm_analysis.analyse_template). Diagnostic uniquement, expose dans
    # l'UI pour signaler que le LLM a propose des zones en conflit.
    dropped_count: int = 0
    # True = l'utilisateur (ou l'auto-validation) a confirme que les zones
    # detectees sont correctes pour ce template. Tant que false, l'export
    # PPTX est refuse (400 ZONES_NOT_VALIDATED). Auto-true si
    # dropped_count == 0 && len(zones) > 0 au write_cache.
    validated: bool = False


class ZoneIn(BaseModel):
    """Body pour POST /documents/<id>/zones — ajout manuel d'une zone.

    kind est force a 'llm' (les zones regex viennent du parsing pptx, pas
    d'un ajout manuel). target doit etre un id de shape ou cellule valide
    visible dans GET /documents/<id>/structure.
    """
    target: str
    label: str
    slide_index: int
    slide_title: str = ""
    location: str = ""
    instruction: str = ""
    align: str = ""


class ZonePatch(BaseModel):
    label: Optional[str] = None
    target: Optional[str] = None
    active: Optional[bool] = None
    instruction: Optional[str] = None
    # ""=auto (preserve l'alignement du template) | left | center | right |
    # justify. Validation des valeurs cote endpoint (patch_zone).
    align: Optional[str] = None


class ZonesValidateIn(BaseModel):
    validated: bool


class StructureBbox(BaseModel):
    """Position d'une shape dans le slide, en EMU (English Metric Unit).
    914400 EMU = 1 pouce. Utilise par le rendu SVG cote UI."""
    left: int
    top: int
    width: int
    height: int


class StructureShape(BaseModel):
    """Une shape ou cellule du template, candidate cible pour ajouter une zone.

    `slide_index` et `slide_title` sont redondants avec `StructureSlide` parent
    mais utiles pour l'UI quand on construit une liste flat des shapes
    (formulaire 'Ajouter une zone').
    """
    id: str
    kind: str                      # "text_box" | "table_cell"
    slide_index: int
    slide_title: str
    location: str
    text: str                      # contenu actuel (tronque, max 300 chars)
    bbox: Optional[StructureBbox] = None


class StructureSlide(BaseModel):
    index: int
    title: str
    shapes: list[StructureShape]


class StructureOut(BaseModel):
    # Dimensions du slide en EMU pour cadrer le viewBox du SVG.
    slide_width_emu: int
    slide_height_emu: int
    slides: list[StructureSlide]


class FlowCell(BaseModel):
    """Cellule d'un tableau dans l'apercu 'flux' Word/PDF."""
    id: str                        # target dp<N> (jointure zone)
    text: str = ""
    has_marker: bool = False       # contient un marqueur regex (XXX/{{cle}})


class FlowBlock(BaseModel):
    """Bloc de l'apercu 'flux' : paragraphe, paragraphe vide, ou tableau.
    `text`/`has_marker` pour paragraphe|empty ; `rows` pour table."""
    type: str                      # "paragraph" | "empty" | "table"
    id: str                        # target dp<N> (paragraphe) ou tbl<N> (table)
    location: str = ""
    text: str = ""
    has_marker: bool = False
    rows: list[list[FlowCell]] = Field(default_factory=list)


class FlowOut(BaseModel):
    """Apercu 'flux document' Word/PDF : blocs dans l'ordre de lecture.
    Pendant lineaire du StructureOut (SVG) reserve au PPTX positionne."""
    blocks: list[FlowBlock] = Field(default_factory=list)


class ZonesBulkDeleteIn(BaseModel):
    """Body pour POST /documents/<id>/zones/bulk-delete."""
    ids: list[str] = Field(default_factory=list)


# ----- Apercu PPTX editable (preview/render decouples) -----------------------


class PptxPreviewOut(BaseModel):
    """Reponse de POST /sessions/<id>/preview-pptx : zones + mapping Mistral
    a editer cote UI avant le rendu definitif."""
    zones: list[ZoneOut]
    mapping: dict[str, str] = Field(default_factory=dict)


class PptxRenderIn(BaseModel):
    """Body de POST /sessions/<id>/render-pptx : mapping (potentiellement
    edite par l'utilisateur dans la modal d'apercu)."""
    mapping: dict[str, str] = Field(default_factory=dict)
    filename: Optional[str] = None


class RefillZonesIn(BaseModel):
    """Body de POST /sessions/<id>/refill-zones : re-genere via Mistral le
    contenu pour un sous-ensemble de zones. `force=True` ajoute une
    instruction qui relache la regle de pertinence (utile pour combler des
    zones vides ou apres edit manuel rate)."""
    zone_ids: list[str] = Field(default_factory=list)
    force: bool = False


class RefillZonesOut(BaseModel):
    """Subset du mapping pour les zones rejoues seulement. Le client fait le
    merge avec le mapping en cours dans la modal."""
    mapping: dict[str, str] = Field(default_factory=dict)


class UploadItemResult(BaseModel):
    filename: str
    ok: bool
    document_id: Optional[uuid.UUID] = None
    skipped: Optional[str] = None
    error: Optional[str] = None
    chunk_count: Optional[int] = None


class UploadResultOut(BaseModel):
    uploaded: list[UploadItemResult]


# ----- Sessions / Messages ---------------------------------------------------


class SessionCreateIn(BaseModel):
    title: Optional[str] = None
    scope_doc_ids: list[uuid.UUID] = Field(default_factory=list)
    lang: str = "fr"
    output_format: str = "markdown"  # markdown | faq | structured | table | template
    length: str = "medium"           # short | medium | long
    tone: str = "professional"       # professional | pedagogical | technical | synthetic
    template_doc_id: Optional[uuid.UUID] = None
    style_doc_id: Optional[uuid.UUID] = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    scope_doc_ids: list[uuid.UUID]
    lang: str
    output_format: str = "markdown"
    length: str = "medium"
    tone: str = "professional"
    template_doc_id: Optional[uuid.UUID] = None
    style_doc_id: Optional[uuid.UUID] = None
    created_at: datetime

    @field_validator("scope_doc_ids", mode="before")
    @classmethod
    def _parse_scope(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                raw = json.loads(v or "[]")
            except json.JSONDecodeError:
                return []
            if not isinstance(raw, list):
                return []
            out: list[str] = []
            for s in raw:
                try:
                    out.append(str(uuid.UUID(s)))
                except (ValueError, TypeError):
                    continue
            return out
        return v


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    citations: list[dict[str, Any]]
    created_at: datetime

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                raw = json.loads(v or "[]")
            except json.JSONDecodeError:
                return []
            return raw if isinstance(raw, list) else []
        return v


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)


# ----- Settings --------------------------------------------------------------


class SettingsIn(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    chat_model: Optional[str] = None
    embed_model: Optional[str] = None
    vision_model: Optional[str] = None
    ocr_model: Optional[str] = None
    llm_enabled: Optional[bool] = None


class SettingsOut(BaseModel):
    api_key_set: bool
    base_url: str
    chat_model: str
    embed_model: str
    vision_model: str
    ocr_model: str
    llm_enabled: bool
    llm_tested: bool = False


class TestConnectionOut(BaseModel):
    ok: bool
    models: list[str] = Field(default_factory=list)
    error: Optional[str] = None


# ----- Prompts (editables runtime via /settings/prompts) ---------------------


class PromptEntryOut(BaseModel):
    value: str
    is_default: bool


class PromptsOut(BaseModel):
    pptx_analysis: PromptEntryOut
    pptx_fill: PromptEntryOut


class PromptsIn(BaseModel):
    # None = champ ignore (pas de changement). Chaine vide = reset au defaut.
    pptx_analysis: Optional[str] = None
    pptx_fill: Optional[str] = None


# ----- Admin -----------------------------------------------------------------


class AdminStatsOut(BaseModel):
    documents: int
    chunks: int
    sessions: int
    messages: int
    total_size_bytes: int


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]
