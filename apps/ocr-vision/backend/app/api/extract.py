"""Routes /api/v1/extract et /api/v1/export.

- POST /extract : upload PDF/image + project_table_id -> OCR (Mistral) puis
  extraction structuree (N lignes suivant les colonnes/regles) -> persiste les
  lignes. Respecte l'interrupteur LLM (OFF -> 200 + 0 ligne, jamais 5xx).
- POST /export  : ecrit un CSV `<projet>__<table>.csv` dans un dossier cible
  (local-first, ecart documente dans le README). 1 CSV par table.
"""

from __future__ import annotations

import csv
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.core.extraction import extract_rows
from app.core.images import extract_images
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled
from app.db.models import ExtractedImage, ExtractedRow, Project, ProjectTable
from app.db.session import get_db
from app.schemas import ExportIn, ExportOut, ExtractOut, RowOut

log = logging.getLogger("ocr-vision.extract")

router = APIRouter(tags=["extract"])


def _load_table(db: Session, table_id: str) -> ProjectTable:
    t = db.get(ProjectTable, table_id)
    if t is None:
        raise AppError("TABLE_NOT_FOUND", "Table introuvable.", status_code=404)
    return t


def _mime_for(file: UploadFile) -> str:
    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        return "application/pdf"
    ctype = (file.content_type or "").lower()
    return ctype if ctype.startswith("image/") else "image/png"


@router.post("/extract", response_model=ExtractOut)
def extract(
    project_table_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ExtractOut:
    table = _load_table(db, project_table_id)
    columns = table.columns or []

    # Interrupteur global LLM (standard) : OFF -> fallback gracieux (0 ligne).
    if not get_llm_enabled(db):
        return ExtractOut(
            rows_added=0,
            rows=[],
            warning="LLM desactive — OCR/extraction ignore.",
        )

    data = file.file.read()
    if not data:
        raise AppError("FILE_EMPTY", "Fichier vide.", status_code=400)

    try:
        client = MistralClient.from_db(db)
    except MistralError as exc:
        raise AppError("MISTRAL_NOT_CONFIGURED", str(exc), status_code=400) from exc

    try:
        ocr_text = client.ocr(data, mime_type=_mime_for(file))
    except Exception as exc:  # noqa: BLE001
        raise AppError("OCR_FAILED", f"OCR : {type(exc).__name__}: {exc}", status_code=502) from exc

    try:
        parsed = extract_rows(client, columns, ocr_text)
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "EXTRACT_FAILED",
            f"Extraction : {type(exc).__name__}: {exc}",
            status_code=502,
        ) from exc

    created: list[ExtractedRow] = []
    for values in parsed:
        row = ExtractedRow(
            project_table_id=table.id,
            source_filename=file.filename or "",
            values=values,
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)

    # Extraction des images/illustrations (PDF uniquement, best-effort).
    images_added = 0
    if _mime_for(file) == "application/pdf":
        out_dir = Path(settings.storage_dir) / table.id
        for meta in extract_images(data, out_dir, uuid.uuid4().hex):
            db.add(
                ExtractedImage(
                    project_table_id=table.id,
                    source_filename=file.filename or "",
                    filename=meta["filename"],
                    page=meta.get("page"),
                )
            )
            images_added += 1
        if images_added:
            db.commit()

    warning = "" if parsed else "Aucune ligne extraite du document."
    return ExtractOut(
        rows_added=len(created),
        rows=[
            RowOut(
                id=r.id,
                source_filename=r.source_filename or "",
                values=r.values or {},
                created_at=r.created_at,
            )
            for r in created
        ],
        images_added=images_added,
        warning=warning,
    )


_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _slug(name: str) -> str:
    s = _SAFE.sub("_", (name or "").strip()).strip("._")
    return s or "table"


def _write_csv(out_path: Path, headers: list[str], keys: list[str], rows: list) -> None:
    # UTF-8 BOM + separateur ';' : ouverture directe dans Excel FR.
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([*headers, "_source", "_extrait_le"])
        for r in rows:
            values = r.values or {}
            line = [values.get(k, "") for k in keys]
            writer.writerow([*line, r.source_filename or "", r.created_at.isoformat()])


def _write_xlsx(out_path: Path, headers: list[str], keys: list[str], rows: list) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Extraction"
    ws.append([*headers, "_source", "_extrait_le"])
    for r in rows:
        values = r.values or {}
        line = [values.get(k, "") for k in keys]
        ws.append([*line, r.source_filename or "", r.created_at.isoformat()])
    wb.save(str(out_path))


@router.post("/export", response_model=ExportOut)
def export_table(payload: ExportIn, db: Session = Depends(get_db)) -> ExportOut:
    table = _load_table(db, payload.project_table_id)
    project = db.get(Project, table.project_id)

    target = Path(payload.target_dir).expanduser()
    if not target.exists() or not target.is_dir():
        raise AppError(
            "TARGET_DIR_INVALID",
            f"Repertoire cible introuvable : {payload.target_dir}",
            status_code=400,
        )

    columns = table.columns or []
    keys = [c.get("key", "") for c in columns]
    headers = [c.get("label") or c.get("key", "") for c in columns]

    rows = db.scalars(
        select(ExtractedRow)
        .where(ExtractedRow.project_table_id == table.id)
        .order_by(ExtractedRow.created_at.asc())
    ).all()

    project_name = project.name if project else "projet"
    ext = "xlsx" if payload.format == "xlsx" else "csv"
    filename = f"{_slug(project_name)}__{_slug(table.name)}.{ext}"
    out_path = (target / filename).resolve()
    # Garde-fou anti-traversee : le fichier doit rester dans le dossier cible.
    if target.resolve() not in out_path.parents:
        raise AppError("TARGET_DIR_INVALID", "Chemin de sortie invalide.", status_code=400)

    if payload.format == "xlsx":
        _write_xlsx(out_path, headers, keys, rows)
    else:
        _write_csv(out_path, headers, keys, rows)

    log.info("export %s table=%s rows=%d path=%s", ext, table.id, len(rows), out_path)
    return ExportOut(path=str(out_path), rows=len(rows), format=ext)
