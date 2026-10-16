"""Version-one persistence contract shared by startup preferences and history."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import UUID4, BaseModel, ConfigDict, Field

from app.services.saved_files import SavedImage, SavedWorkbook


class StateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReplacementPair(StateModel):
    id: int = Field(ge=0)
    reference: str
    replacement: str
    enabled: bool = True


class ExcelColumn(StateModel):
    index: int = Field(ge=1, le=16384)
    letter: str
    header: str
    label: str


class ExcelPiece(StateModel):
    row: int = Field(ge=2, le=1048576)
    name: str


class ExcelPresetState(StateModel):
    workbook: SavedWorkbook | None = None
    sheets: list[str] = Field(default_factory=list)
    sheet: str = ""
    columns: list[ExcelColumn] = Field(default_factory=list)
    reference_column: str = Field(default="", alias="referenceColumn")
    replacement_column: str = Field(default="", alias="replacementColumn")
    icn_column: str = Field(default="", alias="icnColumn")
    piece_column: str = Field(default="", alias="pieceColumn")
    pieces: list[ExcelPiece] = Field(default_factory=list)


class ExcelWorkspaceState(ExcelPresetState):
    piece_row: str = Field(default="", alias="pieceRow")
    pairs: list[ReplacementPair] = Field(default_factory=list)


class OcrLine(StateModel):
    text: str
    confidence: float
    box: list[list[float]]
    matched_references: list[str]


class OcrReference(StateModel):
    reference: str
    found: bool
    line_indices: list[int]
    replacement: str = ""
    replacement_count: int = 0


class OcrAnalysis(StateModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    source_width: int = Field(gt=0)
    source_height: int = Field(gt=0)
    full_text: str
    lines: list[OcrLine]
    references: list[OcrReference]
    filename: str


EditKind = Literal["ocr", "brush-lama", "brush-color"]


class ImageRevision(StateModel):
    image: SavedImage
    analysis: OcrAnalysis | None = None
    kind: EditKind


class Operation(StateModel):
    kind: Literal["ocr", "brush-lama", "brush-color", "undo"]
    at: datetime


class WorkspaceState(StateModel):
    schema_version: Literal[1] = 1
    output_filename: str = ""
    image: SavedImage
    excel: ExcelWorkspaceState
    manual_pairs: list[ReplacementPair] = Field(alias="manualPairs")
    revisions: list[ImageRevision]
    operations: list[Operation]


class HistorySummary(StateModel):
    id: UUID4
    filename: str
    piece_name: str
    created_at: datetime
    updated_at: datetime
    version: int
    operation_count: int


class HistoryDetail(HistorySummary):
    state: WorkspaceState


class HistoryPage(StateModel):
    items: list[HistorySummary]
    next_cursor: UUID4 | None = None
