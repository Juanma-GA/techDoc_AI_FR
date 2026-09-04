"""Routes /api/v1/brex - profils BREX projet (uploades une fois, reutilises).

Un BREX est defini par projet et applique a tous ses documents : c'est ce qui
evite de refaire le mapping a chaque migration.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.brex import parse_brex
from app.core.errors import AppError
from app.core.s1000d_schema import SUPPORTED_ISSUES
from app.db.models import BrexProfile
from app.db.session import get_db
from app.schemas import BrexProfileOut

router = APIRouter(prefix="/brex", tags=["brex"])


def _storage() -> Path:
    p = Path(settings.storage_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _to_out(b: BrexProfile) -> BrexProfileOut:
    return BrexProfileOut(
        id=b.id, name=b.name, s1000d_issue=b.s1000d_issue,
        created_at=b.created_at.isoformat(),
    )


@router.get("", response_model=list[BrexProfileOut])
def list_brex(db: Session = Depends(get_db)) -> list[BrexProfileOut]:
    rows = db.scalars(select(BrexProfile).order_by(BrexProfile.created_at.desc())).all()
    return [_to_out(b) for b in rows]


@router.post("", response_model=BrexProfileOut, status_code=201)
async def upload_brex(
    file: UploadFile = File(...),
    name: str = Form(...),
    s1000d_issue: str = Form("5.0"),
    db: Session = Depends(get_db),
) -> BrexProfileOut:
    if s1000d_issue not in SUPPORTED_ISSUES:
        raise AppError("BAD_ISSUE", f"Issue non supportee : {s1000d_issue}", 422)
    raw = await file.read()
    if len(raw) > settings.max_upload_size_bytes:
        raise AppError("FILE_TOO_LARGE", "Fichier BREX trop volumineux.", 413)
    try:
        xml = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppError("BAD_BREX", "Le BREX n'est pas un XML UTF-8 valide.", 422) from exc
    # Sanity check : le BREX doit contenir au moins une regle de structure.
    if not parse_brex(xml):
        raise AppError(
            "BAD_BREX",
            "Aucune structureObjectRule trouvee : ce fichier ne ressemble pas a un BREX.",
            422,
        )

    profile = BrexProfile(name=name, s1000d_issue=s1000d_issue, xml_path="")
    db.add(profile)
    db.flush()  # genere l'id
    path = _storage() / f"brex_{profile.id}.xml"
    path.write_text(xml, encoding="utf-8")
    profile.xml_path = str(path)
    db.commit()
    return _to_out(profile)
