"""Tests - ecriture du template Excel Catalogue (preservation + coercition)."""

from __future__ import annotations

import io

import openpyxl

from app.config import settings
from app.core.xlsx_fill import fill_catalogue, output_filename


def _items() -> list[dict]:
    return [
        {
            "fig": "10A", "figreflink": 10, "aplomb": ".", "description": "Piece A",
            "matiere": "", "ref_client": "C1", "ref_interne": "I1", "ref_fournisseur": "F1",
            "qty": "2", "symbole": "",
        },
        {
            "fig": "20A", "figreflink": 20, "aplomb": ".", "description": "Piece B",
            "matiere": "", "ref_client": "C2", "ref_interne": "I2", "ref_fournisseur": "F2",
            "qty": "0.5 kg", "symbole": "",
        },
    ]


def _load(data: bytes) -> openpyxl.Workbook:
    return openpyxl.load_workbook(io.BytesIO(data))


def test_fill_preserves_sheets_and_header() -> None:
    data = fill_catalogue(settings.xlsx_template_path, _items(), {})
    wb = _load(data)
    # Feuille Suivi preservee, en-tete Catalogue intact.
    assert "Suivi" in wb.sheetnames
    assert "Catalogue" in wb.sheetnames
    ws = wb["Catalogue"]
    assert [ws.cell(1, c).value for c in range(1, 7)] == [
        "module", "partid", "fig", "figreflink", "aplomb", "description"
    ]


def test_fill_writes_items_from_row2_without_header_meta() -> None:
    data = fill_catalogue(settings.xlsx_template_path, _items(), {})
    ws = _load(data)["Catalogue"]
    # Sans header_meta : pas de bloc en-tete module, articles des la ligne 2.
    assert ws.cell(2, 3).value == "10A"      # C fig
    assert ws.cell(2, 10).value == "I1"      # J bt001_part_no (ref interne)
    assert ws.cell(2, 11).value == "C1"      # K sncf_partno (ref client)
    assert ws.cell(2, 12).value == "F1"      # L pn_supplier (ref fournisseur)


def test_qty_numeric_coercion() -> None:
    ws = _load(fill_catalogue(settings.xlsx_template_path, _items(), {}))["Catalogue"]
    # "2" -> nombre ; "0.5 kg" -> reste du texte.
    assert ws.cell(2, 14).value == 2
    assert isinstance(ws.cell(2, 14).value, int)
    assert ws.cell(3, 14).value == "0.5 kg"


def test_header_meta_builds_module_block() -> None:
    meta = {"module": "F1-PL", "otan_supplier": "NOM FRN", "drw": "F1.png",
            "top_assembly": "+1A", "bom_title": "BOM TEST"}
    ws = _load(fill_catalogue(settings.xlsx_template_path, _items(), meta))["Catalogue"]
    # Bloc en-tete module en lignes 2-3, articles ensuite (ligne 4+).
    assert ws.cell(2, 1).value == "F1-PL"         # A module
    assert ws.cell(2, 20).value == "F1.png"       # T drw
    assert ws.cell(3, 3).value == "+1A"           # C fig (top assembly)
    assert ws.cell(4, 3).value == "10A"           # 1er article
    assert ws.cell(4, 1).value == "F1-PL"         # module repete sur chaque ligne
    assert ws.cell(4, 13).value == "NOM FRN"      # M otan_supplier repete


def test_output_filename() -> None:
    assert output_filename({"module": "F1888-PL001A"}) == "F1888-PL001A.xlsx"
    assert output_filename({}) == "nomenclature.xlsx"
