from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.ecm_rename import preview_batch, process_batch


router = APIRouter(prefix="/ecm-rename", tags=["ecm-rename"])


class PreviewRequest(BaseModel):
    source_path: str = Field(min_length=1)
    tracker_path: str = Field(min_length=1)
    sheet_name: str | None = None
    header_row: int | None = Field(default=None, ge=1)


class TrackerColumn(BaseModel):
    name: str
    index: int
    field: str | None = None


class PreviewRecord(BaseModel):
    source_path: str
    file_name: str
    reference: str
    revision: str
    subject: str
    tracker_values: list[str]


class PreviewResponse(BaseModel):
    source_path: str
    tracker_path: str
    sheet_names: list[str]
    sheet_name: str
    header_row: int
    columns: list[TrackerColumn]
    records: list[PreviewRecord]


class ProcessRecord(BaseModel):
    source_path: str
    reference: str
    revision: str = ""
    subject: str
    tracker_values: list[str]


class ProcessRequest(BaseModel):
    source_path: str
    tracker_path: str
    output_path: str
    sheet_name: str
    header_row: int = Field(ge=1)
    records: list[ProcessRecord] = Field(min_length=1)


class ProcessResponse(BaseModel):
    created_folders: list[str]
    tracker_path: str
    backup_path: str
    rows_written: int


@router.post("/preview", response_model=PreviewResponse)
def preview(payload: PreviewRequest) -> dict[str, Any]:
    return preview_batch(
        payload.source_path,
        payload.tracker_path,
        payload.sheet_name,
        payload.header_row,
    )


@router.post("/process", response_model=ProcessResponse)
def process(payload: ProcessRequest) -> dict[str, Any]:
    return process_batch(
        source_path=payload.source_path,
        tracker_path=payload.tracker_path,
        output_path=payload.output_path,
        sheet_name=payload.sheet_name,
        header_row=payload.header_row,
        records=[record.model_dump() for record in payload.records],
    )