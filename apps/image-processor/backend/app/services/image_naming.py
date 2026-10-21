"""ICN naming for exports and current or previously saved image workspaces."""

from __future__ import annotations

import json

from fastapi import HTTPException
from pydantic import BaseModel, JsonValue
from sqlalchemy.orm import Session

from app.services.excel import extract_excel_replacements, get_excel_sheet, open_excel_workbook
from app.services.image_layout import output_filename
from app.services.workspace_storage import restore_state
from app.workspace_schemas import ExcelWorkspaceState, OcrAnalysis


def excel_output_filename(
    contents: bytes, workbook_name: str | None, excel: ExcelWorkspaceState,
) -> str:
    try:
        columns = (
            int(excel.reference_column), int(excel.replacement_column), int(excel.icn_column),
            int(excel.piece_column), int(excel.piece_row),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Les selections Excel sont incompletes.") from error
    with open_excel_workbook(contents, workbook_name) as workbook:
        worksheet = get_excel_sheet(workbook, excel.sheet)
        _, icn = extract_excel_replacements(worksheet, *columns)
    return output_filename(None, icn)


def workspace_filename(
    source_name: str, excel: ExcelWorkspaceState, analysis_name: str | None, edited: bool,
) -> str:
    if excel.workbook is not None and all((
        excel.sheet, excel.reference_column, excel.replacement_column,
        excel.icn_column, excel.piece_column, excel.piece_row,
    )):
        return excel_output_filename(excel.workbook.contents(), excel.workbook.name, excel)
    if analysis_name is not None:
        return analysis_name
    return output_filename(source_name, None) if edited else source_name


class _RevisionMetadata(BaseModel):
    analysis: OcrAnalysis | None = None


class _NamingMetadata(BaseModel):
    output_filename: str = ""
    excel: dict[str, JsonValue]
    revisions: list[_RevisionMetadata]


def history_filename(db: Session, owner_id: str, encoded: str, previous_name: str) -> str:
    metadata = _NamingMetadata.model_validate_json(encoded)
    if metadata.output_filename:
        return metadata.output_filename
    # Old OCR histories already contain the ICN, including after brush edits.
    analysis = next((item.analysis for item in reversed(metadata.revisions) if item.analysis), None)
    if analysis is not None:
        return analysis.filename
    # Old brush-only histories need just the workbook, never the image payloads.
    excel = ExcelWorkspaceState.model_validate(
        restore_state(db, owner_id, json.dumps(metadata.excel)),
    )
    return workspace_filename(previous_name, excel, None, bool(metadata.revisions))
