"""Resolution des profils CATI (detection PDF + mapping Excel + template)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CatiProfile


def get_profile(db: Session, profile_id: str | None) -> CatiProfile | None:
    """Profil demande, sinon profil par defaut, sinon None."""
    if profile_id:
        p = db.get(CatiProfile, profile_id)
        if p is not None:
            return p
    return db.scalar(select(CatiProfile).where(CatiProfile.is_default.is_(True)))


def _load(raw: str) -> dict[str, Any]:
    try:
        val = json.loads(raw or "{}")
        return val if isinstance(val, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def pdf_map_of(profile: CatiProfile | None) -> dict[str, int]:
    if profile is None:
        return {}
    out: dict[str, int] = {}
    for k, v in _load(profile.pdf_map).items():
        try:
            out[k] = int(v)
        except (TypeError, ValueError):
            continue
    return out


def excel_map_of(profile: CatiProfile | None) -> dict[str, str]:
    if profile is None:
        return {}
    return {str(k): str(v) for k, v in _load(profile.excel_map).items() if v}
