"""Complete, locally stored image workspaces with lightweight cursor listing."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import UUID4
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import FileAsset, ImageHistory
from app.db.session import get_db
from app.services.image_naming import history_filename, workspace_filename
from app.services.workspace_storage import persist_state, purge_assets, restore_state
from app.workspace_schemas import HistoryDetail, HistoryPage, HistorySummary, WorkspaceState

router = APIRouter(prefix="/image-processor/history", tags=["history"])
log = structlog.get_logger(__name__)


def _get_history(db: Session, history_id: UUID) -> ImageHistory:
    record = db.get(ImageHistory, str(history_id))
    if record is None:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return record


def _summary(db: Session, record: ImageHistory) -> HistorySummary:
    return HistorySummary(
        id=record.id,
        filename=history_filename(db, record.id, record.state, record.filename),
        piece_name=record.piece_name,
        created_at=record.created_at.replace(tzinfo=UTC),
        updated_at=record.updated_at.replace(tzinfo=UTC),
        version=record.version,
        operation_count=record.operation_count,
    )


@router.get("", response_model=HistoryPage)
def list_history(
    limit: int = Query(default=30, ge=1, le=100),
    cursor: UUID4 | None = None,
    db: Session = Depends(get_db),
) -> HistoryPage:
    query = select(ImageHistory)
    if cursor is not None:
        previous = _get_history(db, cursor)
        query = query.where(or_(
            ImageHistory.updated_at < previous.updated_at,
            and_(ImageHistory.updated_at == previous.updated_at, ImageHistory.id < previous.id),
        ))
    records = db.scalars(
        query.order_by(ImageHistory.updated_at.desc(), ImageHistory.id.desc()).limit(limit + 1)
    ).all()
    return HistoryPage(
        items=[_summary(db, record) for record in records[:limit]],
        next_cursor=records[limit - 1].id if len(records) > limit else None,
    )


@router.get("/{history_id}", response_model=HistoryDetail)
def read_history(history_id: UUID4, db: Session = Depends(get_db)) -> HistoryDetail:
    record = _get_history(db, history_id)
    return HistoryDetail(
        **_summary(db, record).model_dump(),
        state=WorkspaceState.model_validate(restore_state(db, str(history_id), record.state)),
    )


@router.put("/{history_id}", response_model=HistorySummary)
def save_history(
    history_id: UUID4,
    body: WorkspaceState,
    db: Session = Depends(get_db),
) -> HistorySummary:
    now = datetime.now(UTC).replace(tzinfo=None)
    record = db.get(ImageHistory, str(history_id))
    analysis = next((item.analysis for item in reversed(body.revisions) if item.analysis), None)
    body.output_filename = workspace_filename(
        body.image.name, body.excel, analysis.filename if analysis else None, bool(body.revisions),
    )
    with persist_state(db, str(history_id), body) as (encoded, references):
        if record is None:
            record = ImageHistory(id=str(history_id), created_at=now, version=0)
            db.add(record)
        record.filename = body.output_filename
        record.piece_name = next(
            (piece.name for piece in body.excel.pieces if str(piece.row) == body.excel.piece_row), ""
        )
        record.operation_count = len(body.operations)
        record.updated_at = now
        record.version += 1
        record.state = encoded
    purge_assets(db, str(history_id), keep=references)
    return _summary(db, record)


@router.delete("/{history_id}", status_code=204)
def delete_history(history_id: UUID4, db: Session = Depends(get_db)) -> Response:
    record = db.get(ImageHistory, str(history_id))
    remaining_asset = db.scalar(select(FileAsset.id).where(FileAsset.owner_id == str(history_id)))
    if record is None and remaining_asset is None:
        raise HTTPException(status_code=404, detail="History entry not found.")
    if record is not None:
        db.delete(record)
        db.commit()
    purge_assets(db, str(history_id))
    log.info("image_history_deleted", history_id=str(history_id))
    return Response(status_code=204)
