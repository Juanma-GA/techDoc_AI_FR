from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.services.excel import (
    excel_column_options,
    excel_piece_options,
    get_excel_sheet,
    open_excel_workbook,
    read_excel_upload,
)

router = APIRouter(prefix="/image-replace/excel", tags=["image-replace"])


@router.post("/sheets")
async def get_excel_sheets(workbook: UploadFile = File(...)) -> dict[str, list[str]]:
    contents = await read_excel_upload(workbook)
    with open_excel_workbook(contents, workbook.filename) as excel_workbook:
        return {"sheets": excel_workbook.sheetnames}


@router.post("/columns")
async def get_excel_columns(
    workbook: UploadFile = File(...),
    sheet_name: str = Form(...),
) -> dict[str, list[dict[str, object]]]:
    contents = await read_excel_upload(workbook)
    with open_excel_workbook(contents, workbook.filename) as excel_workbook:
        worksheet = get_excel_sheet(excel_workbook, sheet_name)
        return {"columns": excel_column_options(worksheet)}


@router.post("/pieces")
async def get_excel_pieces(
    workbook: UploadFile = File(...),
    sheet_name: str = Form(...),
    piece_column: int = Form(...),
) -> dict[str, list[dict[str, object]]]:
    contents = await read_excel_upload(workbook)
    with open_excel_workbook(contents, workbook.filename) as excel_workbook:
        worksheet = get_excel_sheet(excel_workbook, sheet_name)
        return {"pieces": excel_piece_options(worksheet, piece_column)}
