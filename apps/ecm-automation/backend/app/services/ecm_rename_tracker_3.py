from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

import xlwings as xw

from app.core.errors import AppError
from app.services.ecm_rename_pdf import field_for_label


@contextmanager
def open_tracker(path: Path, *, read_only: bool = False) -> Iterator[xw.Book]:
    app: xw.App | None = None
    book: xw.Book | None = None
    try:
        try:
            app = xw.App(visible=False, add_book=False)
            app.display_alerts = False
            app.screen_updating = False
            app.api.AskToUpdateLinks = False
            book = app.books.open(
                str(path),
                update_links=False,
                read_only=read_only,
                ignore_read_only_recommended=True,
            )
            if not read_only and book.api.ReadOnly:
                raise AppError(
                    "TRACKER_READ_ONLY",
                    "Excel a ouvert le tracker en lecture seule. Vérifie qu'il n'est pas verrouillé "
                    "et que tu as les droits d'écriture.",
                )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                "INVALID_TRACKER",
                "Impossible de lire le tracker. Vérifie qu'il s'agit d'un fichier Excel valide "
                "et qu'il est fermé.",
            ) from exc

        yield book
    finally:
        try:
            if book is not None:
                book.close()
        finally:
            if app is not None:
                app.quit()


def _max_row(sheet: xw.Sheet) -> int:
    return max(sheet.used_range.last_cell.row, 1)


def _header_row(sheet: xw.Sheet, requested_row: int | None) -> int:
    max_row = _max_row(sheet)
    if requested_row is not None:
        if requested_row < 1 or requested_row > max_row:
            raise AppError("INVALID_HEADER_ROW", "La ligne d'en-têtes choisie n'existe pas dans le tracker.")
        return requested_row

    last_col = max(sheet.used_range.last_cell.column, 1)
    grid = sheet.range((1, 1), (min(max_row, 50), last_col)).options(ndim=2).value

    first_nonempty: int | None = None
    best_row: int | None = None
    best_score = 0
    for row_number, row in enumerate(grid, start=1):
        labels = [str(value).strip() for value in row if value is not None and str(value).strip()]
        if labels and first_nonempty is None:
            first_nonempty = row_number
        score = sum(field_for_label(label) is not None for label in labels)
        if score > best_score:
            best_row, best_score = row_number, score
    selected = best_row or first_nonempty
    if selected is None:
        raise AppError("EMPTY_TRACKER", "Le tracker ne contient pas de ligne d'en-têtes.")
    return selected


def find_tracker_layout(
    book: xw.Book,
    sheet_name: str | None,
    requested_header_row: int | None,
) -> tuple[xw.Sheet, int, list[dict[str, Any]]]:
    if sheet_name is None:
        sheet = book.sheets.active
    elif sheet_name in [item.name for item in book.sheets]:
        sheet = book.sheets[sheet_name]
    else:
        raise AppError("INVALID_SHEET", "L'onglet sélectionné n'existe plus dans le tracker.")

    header_row = _header_row(sheet, requested_header_row)
    last_col = max(sheet.used_range.last_cell.column, 1)
    header_values = sheet.range((header_row, 1), (header_row, last_col)).options(ndim=1).value
    columns = [
        {
            "name": str(value).strip(),
            "index": index,
            "field": field_for_label(str(value).strip()),
        }
        for index, value in enumerate(header_values, start=1)
        if value is not None and str(value).strip()
    ]
    if not columns:
        raise AppError("EMPTY_TRACKER", "Aucun nom de colonne n'a été trouvé sur la ligne d'en-têtes.")
    return sheet, header_row, columns


def _find_table(sheet: xw.Sheet, header_row: int, columns: list[dict[str, Any]]) -> Any | None:
    wanted = {column["index"] for column in columns}
    for table in sheet.api.ListObjects:
        table_range = table.Range
        first_col = table_range.Column
        table_columns = set(range(first_col, first_col + table_range.Columns.Count))
        if table_range.Row == header_row and wanted.issubset(table_columns):
            return table
    return None


def _first_empty_row(
    sheet: xw.Sheet,
    header_row: int,
    columns: list[dict[str, Any]],
    stop_row: int | None = None,
) -> int | None:
    last_row = stop_row if stop_row is not None else _max_row(sheet)
    if last_row <= header_row:
        return header_row + 1 if stop_row is None else None

    first_col = min(column["index"] for column in columns)
    last_col = max(column["index"] for column in columns)
    grid = sheet.range((header_row + 1, first_col), (last_row, last_col)).options(ndim=2).value
    offsets = [column["index"] - first_col for column in columns]
    for offset, row in enumerate(grid):
        if all(row[column_offset] in (None, "") for column_offset in offsets):
            return header_row + 1 + offset
    return None if stop_row is not None else last_row + 1


def _clean(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (str, int, float, bool, date, datetime)):
        return value
    return str(value)


def append_tracker_rows(
    sheet: xw.Sheet,
    header_row: int,
    columns: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> list[int]:
    table = _find_table(sheet, header_row, columns)
    appended_rows: list[int] = []

    for record in records:
        values = list(record["tracker_values"])
        if len(values) != len(columns):
            raise AppError(
                "INVALID_TRACKER_VALUES",
                "Le nombre de valeurs ne correspond pas aux colonnes du tracker.",
            )

        if table is not None:
            body = table.DataBodyRange
            table_last_row = body.Row + body.Rows.Count - 1 if body is not None else header_row
            target_row = _first_empty_row(sheet, header_row, columns, stop_row=table_last_row)
            if target_row is None:
                target_row = table.ListRows.Add().Range.Row
        else:
            target_row = _first_empty_row(sheet, header_row, columns)
            if target_row is None:
                raise AppError("EMPTY_TRACKER_ROW", "Impossible de déterminer la prochaine ligne du tracker.")
            style_row = target_row - 1
            if style_row > header_row:
                last_col = max(column["index"] for column in columns)
                source = sheet.range((style_row, 1), (style_row, last_col))
                destination = sheet.range((target_row, 1), (target_row, last_col))
                source.copy(destination=destination)
                sheet.book.app.api.CutCopyMode = False
                for column in columns:
                    cell = sheet.range((target_row, column["index"]))
                    if not str(cell.formula).startswith("="):
                        cell.clear_contents()

        for column, value in zip(columns, values, strict=True):
            cleaned = _clean(value)
            if cleaned is not None:
                sheet.range((target_row, column["index"])).value = cleaned

        appended_rows.append(target_row)

    return appended_rows


def save_tracker(book: xw.Book) -> None:
    if book.api.ReadOnly:
        raise AppError(
            "TRACKER_READ_ONLY",
            "Excel a ouvert le tracker en lecture seule. Vérifie qu'il n'est pas verrouillé "
            "et que tu as les droits d'écriture.",
        )
    book.save()
