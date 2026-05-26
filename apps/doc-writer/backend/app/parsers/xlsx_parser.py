"""Parseur XLSX/XLSM via openpyxl : chaque feuille linéarisée en lignes CSV-like."""

from __future__ import annotations

from openpyxl import load_workbook  # type: ignore[import-untyped]


def parse(path: str) -> dict[str, str]:
    wb = load_workbook(filename=path, read_only=True, data_only=True)
    parts: list[str] = []
    for sheet in wb.worksheets:
        parts.append(f"# Feuille : {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if v is None else str(v).strip() for v in row]
            row_text = " | ".join(c for c in cells if c)
            if row_text:
                parts.append(row_text)
    wb.close()
    return {"text": "\n".join(parts)}
