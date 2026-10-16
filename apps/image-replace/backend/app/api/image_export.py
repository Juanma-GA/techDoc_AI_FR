"""Download the current image as an ICN-named A4 JPEG without changing revisions."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.services.constants import MAX_IMAGE_BYTES
from app.services.excel import read_excel_upload
from app.services.image_layout import export_jpeg, output_filename
from app.services.image_naming import excel_output_filename
from app.workspace_schemas import ExcelWorkspaceState

router = APIRouter(prefix="/image-replace", tags=["image-replace"])


@router.post("/export", response_class=Response)
async def export_image(
    image: UploadFile = File(...),
    filename: str | None = Form(default=None, max_length=255),
    workbook: UploadFile | None = File(default=None),
    excel_sheet: str | None = Form(default=None),
    excel_reference_column: int | None = Form(default=None),
    excel_replacement_column: int | None = Form(default=None),
    excel_icn_column: int | None = Form(default=None),
    excel_piece_column: int | None = Form(default=None),
    excel_piece_row: int | None = Form(default=None),
) -> Response:
    image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="L'image depasse la limite de 15 Mo.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Le fichier image est vide.")
    selection = (
        excel_sheet, excel_reference_column, excel_replacement_column,
        excel_icn_column, excel_piece_column, excel_piece_row,
    )
    if workbook is None and any(value is not None for value in selection):
        raise HTTPException(status_code=422, detail="Le fichier Excel est requis pour ces selections.")
    if workbook is not None:
        if any(value is None for value in selection):
            raise HTTPException(status_code=422, detail="Termine les selections Excel.")
        excel = ExcelWorkspaceState(
            sheet=excel_sheet or "", reference_column=str(excel_reference_column),
            replacement_column=str(excel_replacement_column), icn_column=str(excel_icn_column),
            piece_column=str(excel_piece_column), piece_row=str(excel_piece_row),
        )
        name = await run_in_threadpool(
            excel_output_filename, await read_excel_upload(workbook), workbook.filename, excel,
        )
    else:
        name = output_filename(image.filename, None) if filename is None else output_filename(None, filename)
    return Response(
        content=await run_in_threadpool(export_jpeg, image_bytes), media_type="image/jpeg",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name, safe='')}",
            "Cache-Control": "no-store",
        },
    )
