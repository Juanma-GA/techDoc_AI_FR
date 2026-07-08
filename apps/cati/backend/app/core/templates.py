"""Resolution et validation des templates Excel de sortie.

Le template de sortie n'est plus fige : l'utilisateur en gere plusieurs dans
l'UI, dont un « par defaut » utilise a l'export. Repli sur le template livre
(`settings.xlsx_template_path`) si aucun n'est enregistre.
"""

from __future__ import annotations

from typing import Any

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.db.models import CatiTemplate


def validate_template_xlsx(path: str, sheet_name: str) -> dict[str, Any]:
    """Verifie que le .xlsx est lisible et contient la feuille attendue.

    Renvoie {sheets, header_columns} ; leve AppError si invalide."""
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001 - openpyxl leve des erreurs variees
        raise AppError(
            "TEMPLATE_INVALID",
            f"Fichier Excel illisible : {type(e).__name__}",
            status_code=400,
        ) from e
    try:
        sheets = list(wb.sheetnames)
        if sheet_name not in sheets:
            raise AppError(
                "TEMPLATE_SHEET_MISSING",
                f"Feuille '{sheet_name}' absente du classeur.",
                status_code=400,
                detail={"sheets": sheets},
            )
        ws = wb[sheet_name]
        header = [str(c.value).strip() if c.value is not None else "" for c in next(ws.iter_rows(max_row=1))]
    finally:
        wb.close()
    return {"sheets": sheets, "header_columns": [h for h in header if h]}


def resolve_template(db: Session) -> dict[str, Any]:
    """Template a utiliser a l'export : le defaut enregistre, sinon le fichier livre."""
    tpl = db.scalar(select(CatiTemplate).where(CatiTemplate.is_default.is_(True)))
    if tpl is None:
        tpl = db.scalar(select(CatiTemplate).order_by(CatiTemplate.created_at.desc()))
    if tpl is not None and tpl.storage_path:
        return {
            "path": tpl.storage_path,
            "sheet_name": tpl.sheet_name,
            "header_row": tpl.header_row,
            "data_start_row": tpl.data_start_row,
            "template_id": tpl.id,
        }
    # Repli : template livre avec l'app.
    return {
        "path": settings.xlsx_template_path,
        "sheet_name": settings.xlsx_sheet_name,
        "header_row": settings.xlsx_header_row,
        "data_start_row": settings.xlsx_data_start_row,
        "template_id": None,
    }
