"""Validation XSD de Data Modules importes."""

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, UploadFile

from app.api_models import DmValidationBatchOut
from app.config import settings
from app.core.dm_validation import validate_dm
from app.core.errors import AppError

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/dms", response_model=DmValidationBatchOut, response_model_exclude_unset=True)
def validate_dms(
    files: list[UploadFile] = File(...),
    issue_overrides: str = Form(default="[]"),
) -> dict:
    """Valide un lot de DM; les Issues optionnelles suivent l'ordre des fichiers."""
    if len(files) > settings.max_validation_files:
        raise AppError("VALIDATION_TOO_MANY_FILES", "Trop de fichiers dans ce lot.", 413)
    try:
        overrides = json.loads(issue_overrides)
    except json.JSONDecodeError as exc:
        raise AppError(
            "VALIDATION_BAD_OVERRIDES",
            "Les versions de validation doivent former un tableau JSON.",
            422,
        ) from exc
    if not isinstance(overrides, list) or any(
        value is not None and not isinstance(value, str) for value in overrides
    ):
        raise AppError(
            "VALIDATION_BAD_OVERRIDES",
            "Les versions de validation doivent former un tableau de textes.",
            422,
        )

    results = []
    remaining = settings.max_upload_size_bytes
    for index, upload in enumerate(files):
        raw = upload.file.read(remaining + 1)
        remaining -= len(raw)
        if remaining < 0:
            raise AppError("FILE_TOO_LARGE", "Lot de validation trop volumineux.", 413)
        results.append(validate_dm(
            raw,
            filename=upload.filename or f"DM-{index + 1}.xml",
            issue_override=overrides[index] if index < len(overrides) else None,
        ))
    return {"results": results}
