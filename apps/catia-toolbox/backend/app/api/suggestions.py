"""Routes suggestions - liste par run, accept/reject (unitaire + lot)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import OptimizationRun, Suggestion
from app.db.session import get_db
from app.schemas import (
    SuggestionBulkStatusIn,
    SuggestionBulkStatusOut,
    SuggestionOut,
    SuggestionStatusIn,
)


router = APIRouter(tags=["suggestions"])

_ALLOWED_STATUSES = {"pending", "accepted", "rejected"}


@router.get("/runs/{run_id}/suggestions", response_model=list[SuggestionOut])
def list_suggestions(
    run_id: uuid.UUID,
    action: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Suggestion]:
    if db.get(OptimizationRun, run_id) is None:
        raise AppError("RUN_NOT_FOUND", "Run introuvable.", status_code=404, detail={"id": str(run_id)})
    stmt = select(Suggestion).where(Suggestion.run_id == run_id)
    if action:
        stmt = stmt.where(Suggestion.action == action)
    if status:
        stmt = stmt.where(Suggestion.status == status)
    if source:
        stmt = stmt.where(Suggestion.source == source)
    return list(db.scalars(stmt.order_by(Suggestion.created_at)))


# IMPORTANT : la route statique `/suggestions/bulk-status` DOIT etre declaree
# AVANT la route parametree `/suggestions/{suggestion_id}` (Starlette matche
# par ordre de declaration ; sinon `bulk-status` est lu comme un UUID -> 405/422).
@router.post("/suggestions/bulk-status", response_model=SuggestionBulkStatusOut)
def bulk_update_status(body: SuggestionBulkStatusIn, db: Session = Depends(get_db)) -> SuggestionBulkStatusOut:
    if body.status not in _ALLOWED_STATUSES:
        raise AppError(
            "SUGGESTION_STATUS_INVALID",
            f"Statut invalide. Valeurs autorisees : {sorted(_ALLOWED_STATUSES)}",
            status_code=400,
            detail={"status": body.status},
        )
    if not body.ids:
        return SuggestionBulkStatusOut(updated=0, status=body.status)
    rows = list(db.scalars(select(Suggestion).where(Suggestion.id.in_(body.ids))))
    for s in rows:
        s.status = body.status
    db.commit()
    return SuggestionBulkStatusOut(updated=len(rows), status=body.status)


@router.patch("/suggestions/{suggestion_id}", response_model=SuggestionOut)
def update_status(
    suggestion_id: uuid.UUID, body: SuggestionStatusIn, db: Session = Depends(get_db)
) -> Suggestion:
    s = db.get(Suggestion, suggestion_id)
    if s is None:
        raise AppError("SUGGESTION_NOT_FOUND", "Suggestion introuvable.", status_code=404, detail={"id": str(suggestion_id)})
    if body.status not in _ALLOWED_STATUSES:
        raise AppError(
            "SUGGESTION_STATUS_INVALID",
            f"Statut invalide. Valeurs autorisees : {sorted(_ALLOWED_STATUSES)}",
            status_code=400,
            detail={"status": body.status},
        )
    s.status = body.status
    db.commit()
    db.refresh(s)
    return s
