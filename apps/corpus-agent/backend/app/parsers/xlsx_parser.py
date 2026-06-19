"""XLSX parser via openpyxl. Ported from legacy."""

from __future__ import annotations

import re
from typing import Any

from openpyxl import load_workbook


DMC_REGEX = re.compile(r"DMC[A-Z0-9\-]{3,}")


def parse_xlsx(path: str) -> dict[str, Any]:
    wb = load_workbook(path, data_only=True, read_only=True)
    lines: list[str] = []
    sections: list[str] = []
    for sheet in wb.worksheets:
        sections.append(sheet.title)
        # Marqueur structuré exploité par les checks pour situer une anomalie
        # (ex. consistency.py extrait l'onglet courant via _locate_section).
        lines.append(f"[ONGLET: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            values = [str(v) for v in row if v is not None]
            if values:
                lines.append(" | ".join(values))
    full_text = "\n".join(lines)
    dmc_codes = sorted(set(DMC_REGEX.findall(full_text)))
    return {
        "text": full_text,
        "images": [],
        "sections": sections,
        "dmc_codes": dmc_codes,
    }
