"""Create and retrieve persisted text-layer PDF comparisons."""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.comparison_report import build_comparison_report, ensure_current_report
from app.core.errors import AppError
from app.core.security import (
    read_upload_limited,
    safe_filename,
    safe_storage_join,
    validate_pdf_bytes,
)
from app.db.comparison_models import DocumentComparison
from app.db.session import get_db

from .comparison_schemas import ComparisonDetail, ComparisonListItem, ComparisonSummary

router = APIRouter(prefix="/comparisons", tags=["comparisons"])
MAX_COMPARISON_FILES = 20
MAX_COMPARISON_TOTAL_BYTES = 800 * 1024 * 1024


def comparison_root() -> Path:
    root = safe_storage_join(Path(settings.storage_dir), "comparisons")
    root.mkdir(parents=True, exist_ok=True)
    return root


def comparison_dir(comparison_id: uuid.UUID) -> Path:
    return safe_storage_join(comparison_root(), comparison_id.hex)


def get_comparison(comparison_id: uuid.UUID, db: Session) -> DocumentComparison:
    row = db.get(DocumentComparison, comparison_id)
    if row is None:
        raise AppError("COMPARISON_NOT_FOUND", "Comparaison introuvable.", status_code=404)
    return row


def _summary(row: DocumentComparison) -> ComparisonSummary | None:
    if not row.ai_summary_json:
        return None
    try:
        return ComparisonSummary.model_validate_json(row.ai_summary_json)
    except ValidationError as exc:
        raise AppError(
            "COMPARISON_SUMMARY_INVALID",
            "La synthèse enregistrée est illisible.",
            status_code=500,
        ) from exc


def _to_detail(row: DocumentComparison, db: Session) -> ComparisonDetail:
    report = ensure_current_report(row, db)
    return ComparisonDetail(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        file_count=row.file_count,
        ai_status=row.ai_status,
        report=report,
        ai_summary=_summary(row),
        ai_summary_truncated=row.ai_summary_truncated,
    )


@router.post("", response_model=ComparisonDetail, status_code=201)
def create_comparison(
    files: list[UploadFile] = File(...),
    reference_index: int = Form(0),
    page_similarity_threshold: int = Form(85, ge=50, le=99),
    db: Session = Depends(get_db),
) -> ComparisonDetail:
    if len(files) < 2 or len(files) > MAX_COMPARISON_FILES:
        raise AppError(
            "COMPARISON_FILE_COUNT",
            f"Choisissez entre 2 et {MAX_COMPARISON_FILES} fichiers PDF.",
            status_code=400,
        )
    if reference_index < 0 or reference_index >= len(files):
        raise AppError("COMPARISON_REFERENCE_INVALID", "Référence invalide.", status_code=400)

    comparison_id = uuid.uuid4()
    root = comparison_root()
    temporary = tempfile.TemporaryDirectory(prefix=f"{comparison_id.hex}-", dir=root)
    temporary_dir = Path(temporary.name)
    final_dir = comparison_dir(comparison_id)
    moved = False
    persisted = False
    try:
        paths: list[Path] = []
        filenames: list[str] = []
        total_bytes = 0
        for index, upload in enumerate(files):
            filename = safe_filename(upload.filename)
            if Path(filename).suffix.lower() != ".pdf":
                raise AppError(
                    "UPLOAD_BAD_EXT",
                    "Extension non supportée — PDF uniquement",
                    status_code=400,
                )
            raw = read_upload_limited(upload, settings.max_upload_size_bytes)
            validate_pdf_bytes(raw, settings.max_upload_size_bytes)
            total_bytes += len(raw)
            if total_bytes > MAX_COMPARISON_TOTAL_BYTES:
                raise AppError(
                    "COMPARISON_TOTAL_TOO_LARGE",
                    "La taille totale de la comparaison dépasse 800 MiB.",
                    status_code=413,
                )
            path = temporary_dir / f"document-{index}.pdf"
            path.write_bytes(raw)
            paths.append(path)
            filenames.append(filename)

        report = build_comparison_report(
            paths,
            filenames,
            reference_index,
            page_similarity_threshold / 100,
        )
        row = DocumentComparison(
            id=comparison_id,
            title=filenames[reference_index],
            file_count=len(files),
            reference_index=reference_index,
            report_json=json.dumps(report, ensure_ascii=False),
        )
        temporary_dir.rename(final_dir)
        moved = True
        db.add(row)
        db.commit()
        persisted = True
        return _to_detail(row, db)
    finally:
        if moved and not persisted and final_dir.exists():
            shutil.rmtree(final_dir)
        temporary.cleanup()


@router.get("", response_model=list[ComparisonListItem])
def list_comparisons(db: Session = Depends(get_db)) -> list[ComparisonListItem]:
    rows = db.scalars(
        select(DocumentComparison).order_by(DocumentComparison.created_at.desc())
    ).all()
    return [
        ComparisonListItem(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            file_count=row.file_count,
            ai_status=row.ai_status,
        )
        for row in rows
    ]


@router.get("/{comparison_id}", response_model=ComparisonDetail)
def get_comparison_detail(
    comparison_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ComparisonDetail:
    return _to_detail(get_comparison(comparison_id, db), db)
