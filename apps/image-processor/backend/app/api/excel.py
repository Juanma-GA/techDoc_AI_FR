from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.services.excel import (
    excel_column_options,
    excel_piece_options,
    extract_excel_replacements,
    get_excel_sheet,
    open_excel_workbook,
    read_excel_upload,
)

router = APIRouter(prefix="/image-processor/excel", tags=["image-processor"])


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
    reference_column: int = Form(...),
    replacement_column: int = Form(...),
    piece_column: int = Form(...),
) -> dict[str, list[dict[str, object]]]:
    contents = await read_excel_upload(workbook)
    with open_excel_workbook(contents, workbook.filename) as excel_workbook:
        worksheet = get_excel_sheet(excel_workbook, sheet_name)
        return {
            "pieces": excel_piece_options(
                worksheet, reference_column, replacement_column, piece_column
            )
        }


@router.post("/pairs")
async def get_excel_pairs(
    workbook: UploadFile = File(...),
    excel_sheet: str = Form(...),
    excel_reference_column: int = Form(...),
    excel_replacement_column: int = Form(...),
    excel_icn_column: int = Form(...),
    excel_piece_column: int = Form(...),
    excel_piece_row: int = Form(...),
) -> dict[str, list[dict[str, str]]]:
    contents = await read_excel_upload(workbook)
    with open_excel_workbook(contents, workbook.filename) as excel_workbook:
        worksheet = get_excel_sheet(excel_workbook, excel_sheet)
        pairs, _ = extract_excel_replacements(
            worksheet,
            excel_reference_column,
            excel_replacement_column,
            excel_icn_column,
            excel_piece_column,
            excel_piece_row,
        )
        return {"pairs": pairs}
