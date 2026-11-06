"""CATPart folder screening and workbook export endpoints."""

from __future__ import annotations

from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import onedrive
from app.core.catpart_diff import compare_folders
from app.core.errors import AppError
from app.core.security import safe_under_root
from app.db.session import get_db

router = APIRouter(prefix="/diff", tags=["diff"])
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CatpartCompareIn(BaseModel):
    old_path: str = Field(min_length=1, max_length=4096)
    new_path: str = Field(min_length=1, max_length=4096)


class CatpartSinMatchOut(BaseModel):
    sin: str
    old_pns: list[str]
    new_pns: list[str]
    old_files: list[str]
    new_files: list[str]


class CatpartSameGeOut(BaseModel):
    sin: str
    pn: str
    old_files: list[str]
    new_files: list[str]


class CatpartSoloOut(BaseModel):
    sin: str
    pn: str
    file: str


class CatpartIssueOut(BaseModel):
    file: str | None
    code: str
    message: str


class CatpartCompareOut(BaseModel):
    status: Literal["complete", "partial", "empty"]
    old_count: int
    new_count: int
    matches: list[CatpartSinMatchOut]
    same_ge: list[CatpartSameGeOut]
    solo_a: list[CatpartSoloOut]
    solo_b: list[CatpartSoloOut]
    issues: list[CatpartIssueOut]


def _compare(body: CatpartCompareIn, db: Session) -> CatpartCompareOut:
    root = onedrive.root_for_scope(db, "input")
    old_path = safe_under_root(root, body.old_path)
    new_path = safe_under_root(root, body.new_path)
    if old_path == new_path:
        raise AppError("CATPART_SAME_FOLDER", "Selectionnez deux dossiers differents.", status_code=400)
    return CatpartCompareOut.model_validate(compare_folders(old_path, new_path))


@router.post("/catparts", response_model=CatpartCompareOut)
def compare_catpart_folders(body: CatpartCompareIn, db: Session = Depends(get_db)) -> CatpartCompareOut:
    return _compare(body, db)


@router.post("/catparts/export.xlsx")
def export_catpart_workbook(body: CatpartCompareIn, db: Session = Depends(get_db)) -> StreamingResponse:
    result = _compare(body, db)
    workbook = _build_workbook(result)
    return StreamingResponse(
        iter([workbook]),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="catpart-ge-screening.xlsx"'},
    )


def _build_workbook(result: CatpartCompareOut) -> bytes:
    workbook = Workbook()
    common = workbook.active
    common.title = "GE communs"
    _append_excel_row(common, ["Catégorie", "SIN", "PN A", "PN B", "Fichiers A", "Fichiers B"])

    for item in result.same_ge:
        _append_excel_row(
            common,
            ["GE pareil", item.sin, item.pn, item.pn, "\n".join(item.old_files), "\n".join(item.new_files)],
        )
    for item in result.matches:
        _append_excel_row(
            common,
            [
                "SIN commun, PN différent",
                item.sin,
                "\n".join(item.old_pns),
                "\n".join(item.new_pns),
                "\n".join(item.old_files),
                "\n".join(item.new_files),
            ],
        )
    _format_sheet(common, {"A": 28, "B": 14, "C": 24, "D": 24, "E": 60, "F": 60})

    for title, files in (("Solo A", result.solo_a), ("Solo B", result.solo_b)):
        sheet = workbook.create_sheet(title)
        _append_excel_row(sheet, ["SIN", "PN", "Fichier"])
        for item in files:
            _append_excel_row(sheet, [item.sin, item.pn, item.file])
        _format_sheet(sheet, {"A": 14, "B": 24, "C": 70})

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _append_excel_row(sheet: Worksheet, values: list[str]) -> None:
    sheet.append(values)
    for cell in sheet[sheet.max_row]:
        if isinstance(cell.value, str):
            cell.data_type = "s"
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    if sheet.max_row == 1:
        for cell in sheet[1]:
            cell.font = Font(bold=True)


def _format_sheet(sheet: Worksheet, column_widths: dict[str, int]) -> None:
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in column_widths.items():
        sheet.column_dimensions[column].width = width
