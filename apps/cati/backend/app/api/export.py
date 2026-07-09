"""Route /api/v1/documents/{doc_id}/export.xlsx - genere le template rempli."""

from __future__ import annotations

import io
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.documents import _get_doc
from app.core.profiles import excel_map_of, get_profile
from app.core.templates import resolve_template
from app.core.xlsx_fill import fill_catalogue, output_filename
from app.db.models import CatiItem
from app.db.session import get_db

log = logging.getLogger("cati.export")

router = APIRouter(prefix="/documents/{doc_id}", tags=["export"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/export.xlsx")
def export_xlsx(doc_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    doc = _get_doc(db, doc_id)

    try:
        header_meta = json.loads(doc.header_meta or "{}")
    except (json.JSONDecodeError, TypeError):
        header_meta = {}

    rows = db.scalars(
        select(CatiItem)
        .where(CatiItem.document_id == doc_id, CatiItem.included.is_(True))
        .order_by(CatiItem.order_index)
    ).all()

    items: list[dict[str, Any]] = []
    for r in rows:
        try:
            items.append(json.loads(r.fields or "{}"))
        except (json.JSONDecodeError, TypeError):
            continue

    profile = get_profile(db, doc.profile_id)
    tpl = resolve_template(db, profile.template_id if profile else None)
    data = fill_catalogue(
        tpl["path"],
        items,
        header_meta,
        sheet_name=tpl["sheet_name"],
        header_row=tpl["header_row"],
        data_start_row=tpl["data_start_row"],
        excel_map=excel_map_of(profile),
    )

    filename = output_filename(header_meta)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(io.BytesIO(data), media_type=XLSX_MEDIA, headers=headers)
