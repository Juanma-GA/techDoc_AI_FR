from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from fastapi import HTTPException, UploadFile
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.services.constants import MAX_EXCEL_BYTES
from app.services.ocr_engine import normalize_reference


async def read_excel_upload(upload: UploadFile) -> bytes:
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in {".xlsx", ".xlsm"}:
        raise HTTPException(status_code=415, detail="Formats acceptés pour Excel : .xlsx et .xlsm.")

    contents = await upload.read(MAX_EXCEL_BYTES + 1)
    if len(contents) > MAX_EXCEL_BYTES:
        raise HTTPException(status_code=413, detail="Le fichier Excel dépasse la limite de 15 Mo.")
    if not contents:
        raise HTTPException(status_code=400, detail="Le fichier Excel est vide.")
    return contents


@contextmanager
def open_excel_workbook(contents: bytes, filename: str | None) -> Iterator[Workbook]:
    extension = Path(filename or "").suffix.lower()
    if extension not in {".xlsx", ".xlsm"}:
        raise HTTPException(status_code=415, detail="Formats acceptés pour Excel : .xlsx et .xlsm.")
    try:
        workbook = load_workbook(BytesIO(contents), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, OSError, ParseError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Le fichier Excel est invalide ou illisible.") from error

    try:
        yield workbook
    except (BadZipFile, InvalidFileException, OSError, ParseError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Le fichier Excel est invalide ou illisible.") from error
    finally:
        workbook.close()


def excel_cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def excel_row_value(row: tuple[object, ...], column: int) -> str:
    return excel_cell_text(row[column - 1] if column <= len(row) else None)


def get_excel_sheet(workbook: Workbook, sheet_name: str) -> Worksheet:
    if sheet_name not in workbook.sheetnames:
        raise HTTPException(status_code=422, detail="L'onglet Excel sélectionné n'existe pas.")
    return workbook[sheet_name]


def excel_column_options(worksheet: Worksheet) -> list[dict[str, object]]:
    column_count = int(worksheet.max_column or 0)
    if column_count == 0:
        return []

    header = next(
        worksheet.iter_rows(min_row=1, max_row=1, max_col=column_count, values_only=True),
        (),
    )
    columns: list[dict[str, object]] = []
    for index in range(1, column_count + 1):
        letter = get_column_letter(index)
        name = excel_row_value(header, index)
        columns.append(
            {
                "index": index,
                "letter": letter,
                "header": name,
                "label": f"{letter} — {name}" if name else f"Colonne {letter}",
            }
        )
    return columns


def _is_piece_header(row: tuple[object, ...], piece_column: int) -> bool:
    return not excel_row_value(row, 2) and bool(excel_row_value(row, piece_column))


def excel_piece_options(worksheet: Worksheet, piece_column: int) -> list[dict[str, object]]:
    column_count = int(worksheet.max_column or 0)
    if piece_column < 1 or piece_column > column_count:
        raise HTTPException(status_code=422, detail="La colonne des noms de pièces est invalide.")

    row_count = int(worksheet.max_row or 1)
    if row_count < 2:
        return []

    options: list[dict[str, object]] = []
    for row_number, row in enumerate(
        worksheet.iter_rows(
            min_row=2,
            max_row=row_count,
            max_col=max(column_count, 2),
            values_only=True,
        ),
        start=2,
    ):
        if _is_piece_header(row, piece_column):
            options.append({"row": row_number, "name": excel_row_value(row, piece_column)})
    return options


def extract_excel_replacements(
    worksheet: Worksheet,
    reference_column: int,
    replacement_column: int,
    icn_column: int,
    piece_column: int,
    piece_row: int,
) -> tuple[list[dict[str, str]], str]:
    column_count = int(worksheet.max_column or 0)
    for column in (reference_column, replacement_column, icn_column, piece_column):
        if column < 1 or column > column_count:
            raise HTTPException(status_code=422, detail="Une des colonnes Excel sélectionnées est invalide.")

    row_count = int(worksheet.max_row or 1)
    if piece_row < 2 or piece_row > row_count:
        raise HTTPException(status_code=422, detail="La ligne de pièce sélectionnée est invalide.")

    replacements: list[dict[str, str]] = []
    icn = ""
    found_piece = False
    for row_number, row in enumerate(
        worksheet.iter_rows(
            min_row=2,
            max_row=row_count,
            max_col=max(column_count, 2),
            values_only=True,
        ),
        start=2,
    ):
        is_header = _is_piece_header(row, piece_column)
        if row_number == piece_row:
            if not is_header:
                raise HTTPException(
                    status_code=422, detail="La ligne sélectionnée n'est pas un titre de pièce valide."
                )
            found_piece = True
            icn = excel_row_value(row, icn_column)
            continue

        if not found_piece:
            continue
        if is_header:
            break

        if not icn:
            icn = excel_row_value(row, icn_column)
        reference = excel_row_value(row, reference_column)
        replacement = excel_row_value(row, replacement_column)
        if not reference and not replacement:
            continue
        if not reference or not replacement:
            raise HTTPException(
                status_code=422,
                detail=f"Le couple de remplacement sur la ligne {row_number} est incomplet.",
            )
        if not normalize_reference(reference):
            raise HTTPException(
                status_code=422,
                detail=f"La référence de la ligne {row_number} ne contient aucune lettre ou aucun chiffre.",
            )
        replacements.append({"reference": reference, "replacement": replacement})

    if not found_piece:
        raise HTTPException(
            status_code=422, detail="La pièce sélectionnée n'a pas été trouvée dans cet onglet."
        )
    if not icn:
        raise HTTPException(status_code=422, detail="La cellule ICN de cette pièce est vide.")
    return replacements, icn
