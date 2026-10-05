from __future__ import annotations

import os
import posixpath
import re
import uuid
from copy import copy
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from openpyxl import load_workbook
from openpyxl.formula.translate import Translator
from openpyxl.utils import coordinate_to_tuple, get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.worksheet.worksheet import Worksheet

from app.core.errors import AppError
from app.services.ecm_rename_pdf import field_for_label

SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOCUMENT_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def load_tracker(path: Path, *, read_only: bool, data_only: bool = False) -> Any:
    try:
        return load_workbook(
            path,
            read_only=read_only,
            data_only=data_only,
            keep_vba=path.suffix.casefold() == ".xlsm",
        )
    except Exception as exc:
        raise AppError(
            "INVALID_TRACKER",
            "Impossible de lire le tracker. Vérifie qu'il s'agit d'un fichier Excel valide "
            "et qu'il est fermé.",
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
) -> list[int]:
    next_row = _next_tracker_row(sheet, header_row, columns)
    style_row = next_row - 1
    appended_rows: list[int] = []
    for offset, record in enumerate(records):
        target_row = next_row + offset
        appended_rows.append(target_row)
        values = list(record["tracker_values"])
        for column_index, column in enumerate(columns):
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
    return appended_rows


def _parse_xml(content: bytes) -> ET.Element:
    for _, (prefix, namespace) in ET.iterparse(BytesIO(content), events=("start-ns",)):
        if not re.fullmatch(r"ns\d+", prefix):
            ET.register_namespace(prefix, namespace)
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    return ET.fromstring(content, parser=parser)


def _serialize_xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _worksheet_part(archive: ZipFile, sheet_name: str) -> str:
    workbook = _parse_xml(archive.read("xl/workbook.xml"))
    relationships = _parse_xml(archive.read("xl/_rels/workbook.xml.rels"))
    sheets = workbook.find(f"{{{SPREADSHEET_NS}}}sheets")
    if sheets is None:
        raise ValueError("Le classeur ne contient aucune feuille.")
    sheet = next((item for item in sheets if item.attrib.get("name") == sheet_name), None)
    if sheet is None:
        raise ValueError("L'onglet sélectionné n'existe plus dans le classeur.")
    relationship_id = sheet.attrib.get(f"{{{DOCUMENT_REL_NS}}}id")
    relationship = next(
        (
            item
            for item in relationships
            if item.attrib.get("Id") == relationship_id
            and item.attrib.get("Type", "").endswith("/worksheet")
        ),
        None,
    )
    if relationship is None:
        raise ValueError("Impossible de trouver le fichier XML de l'onglet sélectionné.")
    target = relationship.attrib["Target"]
    part_name = (
        target.lstrip("/")
        if target.startswith("/")
        else posixpath.normpath(posixpath.join("xl", target))
    )
    if part_name not in archive.namelist():
        raise ValueError("Le fichier XML de l'onglet sélectionné est introuvable.")
    return part_name


def _xml_cell(cell: Any) -> ET.Element | None:
    if cell.value is None and not cell.has_style:
        return None

    attributes = {"r": cell.coordinate}
    if cell.has_style:
        attributes["s"] = str(cell.style_id)
    if cell.data_type == "s":
        attributes["t"] = "inlineStr"
        xml_cell = ET.Element(f"{{{SPREADSHEET_NS}}}c", attributes)
        inline_string = ET.SubElement(xml_cell, f"{{{SPREADSHEET_NS}}}is")
        text = ET.SubElement(inline_string, f"{{{SPREADSHEET_NS}}}t")
        text.text = str(cell.value)
        if text.text != text.text.strip():
            text.set(f"{{{XML_NS}}}space", "preserve")
        return xml_cell

    xml_cell = ET.Element(f"{{{SPREADSHEET_NS}}}c", attributes)
    if cell.data_type == "f":
        formula = str(cell.value)
        ET.SubElement(xml_cell, f"{{{SPREADSHEET_NS}}}f").text = formula.removeprefix("=")
        ET.SubElement(xml_cell, f"{{{SPREADSHEET_NS}}}v")
    elif cell.value is not None:
        if cell.data_type in {"b", "e"}:
            xml_cell.set("t", cell.data_type)
        value = "1" if cell.value is True else "0" if cell.value is False else str(cell.value)
        ET.SubElement(xml_cell, f"{{{SPREADSHEET_NS}}}v").text = value
    return xml_cell


def _row_element(sheet: Worksheet, row_number: int, columns: list[dict[str, Any]]) -> ET.Element:
    row = ET.Element(f"{{{SPREADSHEET_NS}}}row", {"r": str(row_number)})
    for column in columns:
        cell = _xml_cell(sheet.cell(row_number, column["index"]))
        if cell is not None:
            row.append(cell)
    return row


def _merge_row(sheet_data: ET.Element, new_row: ET.Element) -> None:
    row_tag = f"{{{SPREADSHEET_NS}}}row"
    cell_tag = f"{{{SPREADSHEET_NS}}}c"
    row_number = int(new_row.attrib["r"])
    existing_row = next(
        (
            item
            for item in sheet_data
            if item.tag == row_tag and int(item.attrib.get("r", "0")) == row_number
        ),
        None,
    )
    if existing_row is None:
        insertion_index = next(
            (
                index
                for index, item in enumerate(sheet_data)
                if item.tag == row_tag and int(item.attrib.get("r", "0")) > row_number
            ),
            len(sheet_data),
        )
        sheet_data.insert(insertion_index, new_row)
        return

    existing_cells = {item.attrib.get("r"): item for item in existing_row if item.tag == cell_tag}
    for new_cell in new_row:
        reference = new_cell.attrib["r"]
        old_cell = existing_cells.get(reference)
        if old_cell is not None:
            existing_row.remove(old_cell)
        existing_row.append(new_cell)

    children = list(existing_row)
    cells = sorted(
        (item for item in children if item.tag == cell_tag),
        key=lambda item: coordinate_to_tuple(item.attrib["r"])[1],
    )
    other_children = [item for item in children if item.tag != cell_tag]
    for child in children:
        existing_row.remove(child)
    for child in [*cells, *other_children]:
        existing_row.append(child)


def _worksheet_xml(
    content: bytes,
    sheet: Worksheet,
    columns: list[dict[str, Any]],
    appended_rows: list[int],
) -> bytes:
    root = _parse_xml(content)
    sheet_data = root.find(f"{{{SPREADSHEET_NS}}}sheetData")
    if sheet_data is None:
        raise ValueError("L'onglet ne contient pas de zone de données.")
    for row_number in appended_rows:
        _merge_row(sheet_data, _row_element(sheet, row_number, columns))
    dimension = root.find(f"{{{SPREADSHEET_NS}}}dimension")
    if dimension is not None:
        dimension.set("ref", sheet.calculate_dimension())
    return _serialize_xml(root)


def _table_xml_updates(archive: ZipFile, sheet: Worksheet) -> dict[str, bytes]:
    tables = {table.name: table for table in sheet.tables.values()}
    updates: dict[str, bytes] = {}
    for part_name in archive.namelist():
        if not part_name.startswith("xl/tables/") or not part_name.endswith(".xml"):
            continue
        root = _parse_xml(archive.read(part_name))
        table = tables.get(root.attrib.get("name", ""))
        if table is None or root.attrib.get("ref") == table.ref:
            continue
        root.set("ref", table.ref)
        if table.autoFilter is not None:
            auto_filter = root.find(f"{{{SPREADSHEET_NS}}}autoFilter")
            if auto_filter is not None and table.autoFilter.ref:
                auto_filter.set("ref", table.autoFilter.ref)
        updates[part_name] = _serialize_xml(root)
    return updates


def save_tracker(
    tracker: Path,
    sheet: Worksheet,
    columns: list[dict[str, Any]],
    appended_rows: list[int],
) -> None:
    temporary = tracker.with_name(f".{tracker.stem}.{uuid.uuid4().hex}.tmp{tracker.suffix}")
    try:
        with ZipFile(tracker) as original:
            sheet_part = _worksheet_part(original, sheet.title)
            updates = _table_xml_updates(original, sheet)
            updates[sheet_part] = _worksheet_xml(
                original.read(sheet_part),
                sheet,
                columns,
                appended_rows,
            )
            with ZipFile(temporary, "w") as output:
                for entry in original.infolist():
                    content = updates.get(entry.filename)
                    output.writestr(entry, content if content is not None else original.read(entry.filename))
        os.replace(temporary, tracker)
    finally:
        temporary.unlink(missing_ok=True)
