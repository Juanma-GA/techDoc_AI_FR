"""Persist only the workbook and its mapping for a fresh home workflow."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import ExcelPreset
from app.db.session import get_db
from app.services.workspace_storage import persist_state, purge_assets, restore_state
from app.workspace_schemas import ExcelPresetState

router = APIRouter(prefix="/image-processor/workspace", tags=["workspace"])
PRESET_ID = "c4c975cb-d58a-46c4-8d24-466bf86d95e0"


@router.get("/excel", response_model=ExcelPresetState)
def read_excel_preset(db: Session = Depends(get_db)) -> ExcelPresetState:
    preset = db.get(ExcelPreset, PRESET_ID)
    if preset is None:
        return ExcelPresetState()
    return ExcelPresetState.model_validate(restore_state(db, PRESET_ID, preset.state))


@router.put("/excel", response_model=ExcelPresetState)
def save_excel_preset(body: ExcelPresetState, db: Session = Depends(get_db)) -> ExcelPresetState:
    preset = db.get(ExcelPreset, PRESET_ID)
    with persist_state(db, PRESET_ID, body) as (encoded, references):
        if preset is None:
            preset = ExcelPreset(id=PRESET_ID, state=encoded)
            db.add(preset)
        else:
            preset.state = encoded
    purge_assets(db, PRESET_ID, keep=references)
    return body
