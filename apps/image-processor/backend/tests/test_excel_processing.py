from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.services.excel import excel_piece_options, extract_excel_replacements


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Repères"
    sheet.append(["Référence", "Colonne B", "Repère", "ICN", "Pièce"])
    sheet.append([None, "section", None, "ICN-A", "Pompe A"])
    sheet.append(["R-001", "ligne de couple", "N-001", None, None])
    sheet.append(["R-002", "ligne de couple", "N-002", None, None])
    sheet.append([None, "section", None, "ICN-B", "Pompe B"])
    sheet.append(["R-101", "ligne de couple", "N-101", None, None])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _excel_upload(data: bytes) -> dict[str, tuple[str, bytes, str]]:
    return {
        "workbook": (
            "mapping.xlsx",
            data,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


def test_excel_sheet_route_lists_workbook_sheets(client: TestClient) -> None:
    response = client.post(
        "/api/v1/image-replace/excel/sheets",
        files=_excel_upload(_workbook_bytes()),
    )

    assert response.status_code == 200
    assert response.json() == {"sheets": ["Repères"]}


def test_excel_columns_route_returns_header_names(client: TestClient) -> None:
    response = client.post(
        "/api/v1/image-replace/excel/columns",
        files=_excel_upload(_workbook_bytes()),
        data={"sheet_name": "Repères"},
    )

    assert response.status_code == 200
    assert response.json()["columns"][0] == {
        "index": 1,
        "letter": "A",
        "header": "Référence",
        "label": "A — Référence",
    }


def test_excel_pieces_route_lists_only_section_headers(client: TestClient) -> None:
    response = client.post(
        "/api/v1/image-replace/excel/pieces",
        files=_excel_upload(_workbook_bytes()),
        data={"sheet_name": "Repères", "reference_column": "1", "piece_column": "5"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "pieces": [
            {"row": 2, "name": "Pompe A"},
            {"row": 5, "name": "Pompe B"},
        ]
    }


def test_excel_pairs_route_extracts_selected_piece_pairs(client: TestClient) -> None:
    response = client.post(
        "/api/v1/image-replace/excel/pairs",
        files=_excel_upload(_workbook_bytes()),
        data={
            "excel_sheet": "Repères",
            "excel_reference_column": "1",
            "excel_replacement_column": "3",
            "excel_icn_column": "4",
            "excel_piece_column": "5",
            "excel_piece_row": "2",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "pairs": [
            {"reference": "R-001", "replacement": "N-001"},
            {"reference": "R-002", "replacement": "N-002"},
        ]
    }


def test_selected_piece_extracts_pairs_until_next_section() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Référence", "Colonne B", "Repère", "ICN", "Pièce"])
    sheet.append([None, "section", None, "ICN-A", "Pompe A"])
    sheet.append(["R-001", "ligne de couple", "N-001", None, None])
    sheet.append(["R-002", "ligne de couple", "N-002", None, None])
    sheet.append([None, "section", None, "ICN-B", "Pompe B"])

    replacements, icn = extract_excel_replacements(
        sheet,
        reference_column=1,
        replacement_column=3,
        icn_column=4,
        piece_column=5,
        piece_row=2,
    )

    assert icn == "ICN-A"
    assert replacements == [
        {"reference": "R-001", "replacement": "N-001"},
        {"reference": "R-002", "replacement": "N-002"},
    ]


def test_excel_piece_options_use_selected_reference_column() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Référence", "Colonne B", "Repère", "ICN", "Pièce"])
    sheet.append([None, "section", None, "ICN-A", "Pompe A"])
    sheet.append(["R-001", "contenu", "N-001", None, None])
    sheet.append(["R-002", "non vide", None, None, "Pas une pièce"])

    assert excel_piece_options(sheet, reference_column=1, piece_column=5) == [
        {"row": 2, "name": "Pompe A"}
    ]
