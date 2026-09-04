"""Routes /api/v1/brdps - CRUD sur les enregistrements BRDP."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.demo_data import DEMO_BRDPS
from app.db.models import Brdp
from app.db.session import get_db
from app.schemas import BrdpIn, BrdpOut

log = logging.getLogger("brdp_manager.brdps")

router = APIRouter(prefix="/brdps", tags=["brdps"])


def _to_out(row: Brdp) -> BrdpOut:
    try:
        history = json.loads(row.history or "[]")
    except json.JSONDecodeError:
        history = []
    return BrdpOut(
        id=row.id,
        identifier=row.identifier,
        title=row.title,
        definition=row.definition,
        proposal=row.proposal,
        validation=row.validation,
        comments=row.comments,
        comment=row.comments,
        history=history,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[BrdpOut])
def list_brdps(db: Session = Depends(get_db)) -> list[BrdpOut]:
    rows = db.query(Brdp).order_by(Brdp.identifier.asc()).all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=BrdpOut)
def create_brdp(payload: BrdpIn, db: Session = Depends(get_db)) -> BrdpOut:
    if db.get(Brdp, payload.id):
        raise HTTPException(status_code=409, detail="BRDP already exists")
    row = Brdp(
        id=payload.id,
        identifier=payload.identifier or payload.id,
        title=payload.title or "",
        definition=payload.definition or "",
        proposal=payload.proposal or "",
        validation=payload.validation or "Pending",
        comments=payload.comments or payload.comment or "",
        history=json.dumps(payload.history or []),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.put("/{brdp_id}", response_model=BrdpOut)
def update_brdp(brdp_id: str, payload: BrdpIn, db: Session = Depends(get_db)) -> BrdpOut:
    row = db.get(Brdp, brdp_id)
    if row is None:
        raise HTTPException(status_code=404, detail="BRDP not found")
    row.identifier = payload.identifier or brdp_id
    row.title = payload.title or ""
    row.definition = payload.definition or ""
    row.proposal = payload.proposal or ""
    row.validation = payload.validation or "Pending"
    row.comments = payload.comments or payload.comment or ""
    if payload.history is not None:
        row.history = json.dumps(payload.history)
    db.commit()
    db.refresh(row)
    return _to_out(row)


def _require_confirm_token(confirm_token: str) -> None:
    """HR9 / rule #13: no destructive delete without explicit confirmation.
    The frontend enforces the double-click pattern before ever calling these
    endpoints; this is the server-side backstop for direct API callers."""
    if not confirm_token or len(confirm_token) < 10:
        raise HTTPException(
            status_code=422,
            detail="Deletion requires confirmation. Use the double-click pattern in UI.",
        )


@router.delete("/{brdp_id}")
def delete_brdp(
    brdp_id: str,
    db: Session = Depends(get_db),
    confirm_token: str = Query("", min_length=0),
) -> dict[str, bool]:
    _require_confirm_token(confirm_token)
    row = db.get(Brdp, brdp_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.delete("")
def delete_all_brdps(
    db: Session = Depends(get_db),
    confirm_token: str = Query("", min_length=0),
) -> dict[str, bool]:
    _require_confirm_token(confirm_token)
    db.query(Brdp).delete()
    db.commit()
    return {"ok": True}


@router.post("/reset-demo", response_model=list[BrdpOut])
def reset_to_demo(db: Session = Depends(get_db)) -> list[BrdpOut]:
    """Efface les BRDPs et recharge le jeu de demonstration."""
    db.query(Brdp).delete()
    for demo in DEMO_BRDPS:
        db.add(
            Brdp(
                id=demo["id"],
                identifier=demo.get("identifier", demo["id"]),
                title=demo.get("title", ""),
                definition=demo.get("definition", ""),
                proposal=demo.get("proposal", ""),
                validation=demo.get("validation", "Pending"),
                comments=demo.get("comment", demo.get("comments", "")),
                history=json.dumps(demo.get("history", [])),
            )
        )
    db.commit()
    rows = db.query(Brdp).order_by(Brdp.identifier.asc()).all()
    return [_to_out(r) for r in rows]
