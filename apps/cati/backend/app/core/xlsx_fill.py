"""Moteur d'ecriture du template Excel "Catalogue" (cati).

Charge le template fixe (openpyxl, sans `read_only`/`data_only` pour conserver
styles et formules), ecrit une ligne par article a partir de `data_start_row`,
et PRESERVE tout le reste : feuille `Suivi`, ligne d'en-tete (ligne 1), noms
definis (`_FilterDatabase`), largeurs de colonnes, styles.

Le style de la ligne-modele (`data_start_row` du template) est clone sur chaque
ligne ecrite via `copy(cell._style)` (StyleArray : font/fill/border/alignment/
number_format d'un coup) — necessaire car `insert_rows`/l'ecriture nue ne
copient pas le formatage.

Les valeurs numeriques pures (quantite, figreflink) sont ecrites en nombre ;
sinon en texte (ex. "0.5 kg" reste du texte, comme dans l'exemple fourni).
"""

from __future__ import annotations

import io
from copy import copy
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from app.core.catalogue_schema import (
    CATALOGUE_COLUMNS,
    item_to_row,
    module_header_rows,
)
from app.core.errors import AppError

# Colonnes ou l'on tente une conversion numerique (nombre pur -> int/float).
_NUMERIC_COLUMNS = {"qty_assy", "figreflink", "nposte"}


def _coerce(col_key: str, value: Any) -> Any:
    """Nombre pur -> int/float pour les colonnes numeriques ; sinon texte."""
    if value is None:
        return None
    if col_key not in _NUMERIC_COLUMNS:
        return value
    if isinstance(value, (int, float)):
        return value
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    try:
        f = float(s)
    except ValueError:
        return value  # ex. "0.5 kg" : on garde le texte
    return int(f) if f.is_integer() else f


def fill_catalogue(
    template_path: str,
    items: list[dict[str, Any]],
    header_meta: dict[str, Any] | None = None,
    *,
    sheet_name: str = "Catalogue",
    header_row: int = 1,
    data_start_row: int = 2,
) -> bytes:
    """Remplit le template et renvoie les bytes du .xlsx.

    `items` : articles (champs logiques). `header_meta` : constantes document.
    """
    meta = header_meta or {}
    try:
        wb = load_workbook(template_path)  # ni read_only ni data_only : on garde tout
    except Exception as e:  # noqa: BLE001
        raise AppError(
            "TEMPLATE_READ_FAILED",
            f"Lecture du template Excel impossible : {type(e).__name__}",
            status_code=500,
        ) from e

    if sheet_name not in wb.sheetnames:
        raise AppError(
            "TEMPLATE_SHEET_MISSING",
            f"Feuille '{sheet_name}' absente du template.",
            status_code=500,
            detail={"sheets": list(wb.sheetnames)},
        )
    ws = wb[sheet_name]

    # Bloc en-tete module (0/1/2 lignes) + une ligne par article.
    rows: list[dict[str, Any]] = module_header_rows(meta)
    rows += [item_to_row(it, meta) for it in items]

    # Style de reference : la ligne-modele du template (si stylee).
    col_count = len(CATALOGUE_COLUMNS)
    style_cache = [ws.cell(row=data_start_row, column=c) for c in range(1, col_count + 1)]

    for offset, row_dict in enumerate(rows):
        target_row = data_start_row + offset
        for c in range(1, col_count + 1):
            col_key = CATALOGUE_COLUMNS[c - 1]
            dst = ws.cell(row=target_row, column=c)
            # Clone le style de la ligne-modele (robustesse : templates styl=es).
            if offset > 0:
                src = style_cache[c - 1]
                dst._style = copy(src._style)
                dst.number_format = src.number_format
            value = _coerce(col_key, row_dict.get(col_key))
            dst.value = value

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def output_filename(header_meta: dict[str, Any] | None, fallback: str = "nomenclature") -> str:
    """Nom de fichier de sortie propose (base sur le code module si dispo)."""
    module = (header_meta or {}).get("module")
    base = str(module).strip() if module else fallback
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in base) or fallback
    return f"{safe}.xlsx"
