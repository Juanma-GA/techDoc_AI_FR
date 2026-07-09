"""Routes /api/v1/profiles - profils CATI (detection PDF + mapping Excel).

Un profil regroupe : les overrides de detection PDF ({champ: index colonne}),
le mapping cible Excel ({champ: cle colonne}) et un template lie. Selectionnable
a l'import pour gerer plusieurs formats/fournisseurs sans toucher au code.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import CatiProfile
from app.db.session import get_db
from app.schemas import ProfileIn, ProfileOut

log = logging.getLogger("cati.profiles")

router = APIRouter(prefix="/profiles", tags=["profiles"])

# Champs autorises (garde-fou : on n'accepte que des cles connues).
PDF_FIELDS = {"fig", "designation", "symbole", "code", "reference", "qty"}
ITEM_FIELDS = {
    "fig", "figreflink", "aplomb", "description", "matiere",
    "ref_client", "ref_interne", "ref_fournisseur", "qty", "symbole",
}


def _profile_out(p: CatiProfile) -> ProfileOut:
    def _load(raw: str) -> dict[str, Any]:
        try:
            v = json.loads(raw or "{}")
            return v if isinstance(v, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    return ProfileOut(
        id=p.id,
        name=p.name,
        is_default=p.is_default,
        template_id=p.template_id,
        pdf_map={k: int(v) for k, v in _load(p.pdf_map).items()},
        excel_map={str(k): str(v) for k, v in _load(p.excel_map).items()},
        created_at=p.created_at.isoformat() if p.created_at else "",
    )


def _clean_pdf_map(m: dict[str, int]) -> dict[str, int]:
    return {k: int(v) for k, v in m.items() if k in PDF_FIELDS and v is not None}


def _clean_excel_map(m: dict[str, str]) -> dict[str, str]:
    return {k: str(v) for k, v in m.items() if k in ITEM_FIELDS and v}


def _get(db: Session, pid: str) -> CatiProfile:
    p = db.get(CatiProfile, pid)
    if p is None:
        raise AppError("PROFILE_NOT_FOUND", "Profil introuvable.", status_code=404)
    return p


@router.get("", response_model=list[ProfileOut])
def list_profiles(db: Session = Depends(get_db)) -> list[ProfileOut]:
    rows = db.scalars(select(CatiProfile).order_by(CatiProfile.created_at.desc())).all()
    return [_profile_out(p) for p in rows]


@router.post("", response_model=ProfileOut)
def create_profile(payload: ProfileIn, db: Session = Depends(get_db)) -> ProfileOut:
    p = CatiProfile(
        name=payload.name.strip() or "Profil",
        template_id=payload.template_id,
        pdf_map=json.dumps(_clean_pdf_map(payload.pdf_map), ensure_ascii=False),
        excel_map=json.dumps(_clean_excel_map(payload.excel_map), ensure_ascii=False),
    )
    if db.scalar(select(CatiProfile).where(CatiProfile.is_default.is_(True))) is None:
        p.is_default = True
    db.add(p)
    db.commit()
    return _profile_out(p)


@router.put("/{pid}", response_model=ProfileOut)
def update_profile(pid: str, payload: ProfileIn, db: Session = Depends(get_db)) -> ProfileOut:
    p = _get(db, pid)
    p.name = payload.name.strip() or p.name
    p.template_id = payload.template_id
    p.pdf_map = json.dumps(_clean_pdf_map(payload.pdf_map), ensure_ascii=False)
    p.excel_map = json.dumps(_clean_excel_map(payload.excel_map), ensure_ascii=False)
    db.commit()
    return _profile_out(p)


@router.post("/{pid}/default", response_model=ProfileOut)
def set_default(pid: str, db: Session = Depends(get_db)) -> ProfileOut:
    p = _get(db, pid)
    db.execute(update(CatiProfile).values(is_default=False))
    p.is_default = True
    db.commit()
    return _profile_out(p)


@router.delete("/{pid}", response_model=ProfileOut)
def delete_profile(pid: str, db: Session = Depends(get_db)) -> ProfileOut:
    p = _get(db, pid)
    out = _profile_out(p)
    was_default = p.is_default
    db.delete(p)
    db.flush()
    if was_default:
        nxt = db.scalar(select(CatiProfile).order_by(CatiProfile.created_at.desc()))
        if nxt is not None:
            nxt.is_default = True
    db.commit()
    return out
