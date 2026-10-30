"""Validation XSD de Data Modules importes."""

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.dm_validation import validate_dm

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/dms")
def validate_dms(
    files: list[UploadFile] = File(...),
    issue_overrides: str = Form(default="[]"),
) -> dict:
    """Valide un lot de DM; les Issues optionnelles suivent l'ordre des fichiers."""
    try:
        overrides = json.loads(issue_overrides)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="issue_overrides doit être un tableau JSON.") from exc
    if not isinstance(overrides, list) or any(
        value is not None and not isinstance(value, str) for value in overrides
    ):
        raise HTTPException(status_code=422, detail="issue_overrides doit être un tableau de versions.")

    results = []
    for index, upload in enumerate(files):
        results.append(validate_dm(
            upload.file.read(),
            filename=upload.filename or f"DM-{index + 1}.xml",
            issue_override=overrides[index] if index < len(overrides) else None,
        ))
    return {"results": results}