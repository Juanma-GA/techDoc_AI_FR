from __future__ import annotations

import os
import shutil
import uuid
from copy import copy
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.formula.translate import Translator
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.worksheet.worksheet import Worksheet

from app.core.errors import AppError
from app.services.ecm_rename_pdf import field_for_label


def load_tracker(path: Path, *, read_only: bool, data_only: bool = False) -> Any:
    try:
        return load_workbook(
            path,
            read_only=read_only,
            data_only=data_only,
            keep_vba=path.suffix.casefold() == ".xlsm",
        )
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "INVALID_TRACKER",
            "Impossible de lire le tracker. Vérifie qu'il s'agit d'un fichier Excel valide et qu'il est fermé.",
        ) from exc


def _header_row(sheet: Worksheet, requested_row: int | None) -> int:
    if requested_row is not None:
        if requested_row < 1 or requested_row > max(sheet.max_row, 1):
            raise AppError("INVALID_HEADER_ROW", "La ligne d'en-têtes choisie n'existe pas dans le tracker.")
        return requested_row

    first_nonempty: int | None = None
    best_row: int | None = None
    best_score = 0
    for row_number in range(1, min(max(sheet.max_row, 1), 50) + 1):
        values = [cell.value for cell in sheet[row_number]]
        labels = [str(value).strip() for value in values if value is not None and str(value).strip()]
        if labels and first_nonempty is None:
            first_nonempty = row_number
        score = sum(field_for_label(label) is not None for label in labels)
        if score > best_score:
            best_row = row_number
            best_score = score
    selected = best_row or first_nonempty
    if selected is None:
        raise AppError("EMPTY_TRACKER", "Le tracker ne contient pas de ligne d'en-têtes.")
    return selected


def find_tracker_layout(
    workbook: Any,
    sheet_name: str | None,
    requested_header_row: int | None,
) -> tuple[Worksheet, int, list[dict[str, Any]]]:
    if sheet_name is None:
        sheet = workbook.active
    elif sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
    else:
        raise AppError("INVALID_SHEET", "L'onglet sélectionné n'existe plus dans le tracker.")

    header_row = _header_row(sheet, requested_header_row)
    columns = [
        {
            "name": str(cell.value).strip(),
            "index": cell.column,
            "field": field_for_label(str(cell.value).strip()),
        }
        for cell in sheet[header_row]
        if cell.value is not None and str(cell.value).strip()
    ]
    if not columns:
        raise AppError("EMPTY_TRACKER", "Aucun nom de colonne n'a été trouvé sur la ligne d'en-têtes.")
    return sheet, header_row, columns


def _next_tracker_row(sheet: Worksheet, header_row: int, columns: list[dict[str, Any]]) -> int:
    indexes = [column["index"] for column in columns]
    for row_number in range(sheet.max_row, header_row, -1):
        if any(sheet.cell(row_number, index).value not in (None, "") for index in indexes):
            return row_number + 1
    return header_row + 1


def _extend_tables(sheet: Worksheet, header_row: int, last_row: int, columns: list[dict[str, Any]]) -> None:
    column_indexes = {column["index"] for column in columns}
    for table in sheet.tables.values():
        min_column, min_row, max_column, max_row = range_boundaries(table.ref)
        table_columns = set(range(min_column, max_column + 1))
        if min_row != header_row or not column_indexes.issubset(table_columns) or max_row >= last_row:
            continue
        table.ref = f"{get_column_letter(min_column)}{min_row}:{get_column_letter(max_column)}{last_row}"
        if table.autoFilter is not None:
            table.autoFilter.ref = table.ref


def append_tracker_rows(
    sheet: Worksheet,
    header_row: int,
    columns: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> None:
    next_row = _next_tracker_row(sheet, header_row, columns)
    style_row = next_row - 1
    for offset, record in enumerate(records):
        target_row = next_row + offset
        values = list(record["tracker_values"])
        for column_index, column in enumerate(columns):
            if column["field"] in {"reference", "revision", "subject"}:
                values[column_index] = record[column["field"]]
            cell = sheet.cell(target_row, column["index"])
            source_cell = sheet.cell(style_row, column["index"])
            if source_cell.has_style:
                cell._style = copy(source_cell._style)
            value = values[column_index]
            if value:
                cell.value = value
                cell.data_type = "s"
            elif source_cell.data_type == "f":
                cell.value = Translator(source_cell.value, origin=source_cell.coordinate).translate_formula(
                    cell.coordinate
                )
            else:
                cell.value = None
        style_row = target_row
    _extend_tables(sheet, header_row, next_row + len(records) - 1, columns)


def _backup_path(tracker: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return tracker.with_name(f"{tracker.stem}_backup_{stamp}{tracker.suffix}")


def save_tracker(workbook: Any, tracker: Path) -> Path:
    backup = _backup_path(tracker)
    temporary = tracker.with_name(f".{tracker.stem}.{uuid.uuid4().hex}.tmp{tracker.suffix}")
    try:
        shutil.copy2(tracker, backup)
        workbook.save(temporary)
        os.replace(temporary, tracker)
    finally:
        temporary.unlink(missing_ok=True)
    return backup


def restore_tracker(backup: Path, tracker: Path) -> None:
    shutil.copy2(backup, tracker)