from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import PathPreference
from app.db.session import get_db
from app.services.ecm_rename import append_tracker_batch, create_folders_batch, preview_batch
from app.services.path_picker import BrowseKind, BrowseLanguage, choose_path

router = APIRouter(prefix="/ecm-rename", tags=["ecm-rename"])


class PreviewRequest(BaseModel):
    source_path: str = Field(min_length=1)
    tracker_path: str = Field(min_length=1)
    sheet_name: str | None = None
    header_row: int | None = Field(default=None, ge=1)
    folder_mode: Literal["create", "rename"] = "create"


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


class FolderRecord(BaseModel):
    source_path: str
    reference: str
    revision: str = ""
    subject: str


class CreateFoldersRequest(BaseModel):
    source_path: str
    output_path: str
    records: list[FolderRecord] = Field(min_length=1)
    folder_mode: Literal["create", "rename"] = "create"


class CreateFoldersResponse(BaseModel):
    created_folders: list[str]
    existing_folders: list[str]
    renamed_folders: list[str] = Field(default_factory=list)


class TrackerRecord(BaseModel):
    tracker_values: list[str]


class AppendTrackerRequest(BaseModel):
    tracker_path: str
    sheet_name: str
    header_row: int = Field(ge=1)
    records: list[TrackerRecord] = Field(min_length=1)


class AppendTrackerResponse(BaseModel):
    tracker_path: str
    rows_written: int


class BrowseRequest(BaseModel):
    kind: BrowseKind
    current_path: str | None = None
    language: BrowseLanguage = "fr"


class BrowseResponse(BaseModel):
    paths: list[str] = Field(default_factory=list)


class PathPreferences(BaseModel):
    source_path: str = ""
    tracker_path: str = ""
    output_path: str = ""


@router.get("/paths", response_model=PathPreferences)
def read_paths(db: Session = Depends(get_db)) -> PathPreferences:
    saved = db.get(PathPreference, 1)
    if saved is None:
        return PathPreferences()
    return PathPreferences(
        source_path=saved.source_path,
        tracker_path=saved.tracker_path,
        output_path=saved.output_path,
    )


@router.put("/paths", response_model=PathPreferences)
def write_paths(payload: PathPreferences, db: Session = Depends(get_db)) -> PathPreferences:
    saved = db.get(PathPreference, 1)
    if saved is None:
        db.add(PathPreference(id=1, **payload.model_dump()))
    else:
        saved.source_path = payload.source_path
        saved.tracker_path = payload.tracker_path
        saved.output_path = payload.output_path
    db.commit()
    return payload


@router.post("/browse", response_model=BrowseResponse)
def browse_path(payload: BrowseRequest) -> BrowseResponse:
    return BrowseResponse(paths=choose_path(payload.kind, payload.current_path, payload.language) or [])


@router.post("/preview", response_model=PreviewResponse)
def preview(payload: PreviewRequest) -> dict[str, Any]:
    return preview_batch(
        payload.source_path,
        payload.tracker_path,
        payload.sheet_name,
        payload.header_row,
        payload.folder_mode,
    )


@router.post("/folders", response_model=CreateFoldersResponse)
def create_folders(payload: CreateFoldersRequest) -> dict[str, Any]:
    return create_folders_batch(
        source_path=payload.source_path,
        output_path=payload.output_path,
        records=[record.model_dump() for record in payload.records],
        folder_mode=payload.folder_mode,
    )


@router.post("/tracker", response_model=AppendTrackerResponse)
def append_tracker(payload: AppendTrackerRequest) -> dict[str, Any]:
    return append_tracker_batch(
        tracker_path=payload.tracker_path,
        sheet_name=payload.sheet_name,
        header_row=payload.header_row,
        records=[record.model_dump() for record in payload.records],
    )
