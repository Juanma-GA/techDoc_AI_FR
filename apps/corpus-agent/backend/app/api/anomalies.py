"""GET /api/v1/projects/{id}/anomalies + PATCH /api/v1/anomalies/{id}
+ GET /api/v1/projects/{id}/anomalies/export.csv."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Anomaly, Project
from app.db.session import get_db
from app.schemas import AnomalyBulkStatusIn, AnomalyBulkStatusOut, AnomalyOut, AnomalyStatusIn


router = APIRouter(tags=["anomalies"])


_ALLOWED_STATUSES = {"open", "acknowledged", "fixed", "rejected"}


@router.get("/projects/{project_id}/anomalies", response_model=list[AnomalyOut])
def list_anomalies(
    project_id: uuid.UUID,
    type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    file_version_id: Optional[uuid.UUID] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Anomaly]:
    stmt = select(Anomaly).where(Anomaly.project_id == project_id)
    if type:
        stmt = stmt.where(Anomaly.type == type)
    if severity:
        stmt = stmt.where(Anomaly.severity == severity)
    if status:
        stmt = stmt.where(Anomaly.status == status)
    if file_version_id:
        stmt = stmt.where(Anomaly.file_version_id == file_version_id)
    return list(db.scalars(stmt.order_by(Anomaly.created_at.desc())))


# IMPORTANT: la route statique `/anomalies/bulk-status` DOIT être déclarée
# AVANT la route paramétrée `/anomalies/{anomaly_id}`. Starlette matche les
# routes par ordre de déclaration : si la paramétrée passe en premier, un
# POST sur `bulk-status` est résolu comme `anomaly_id="bulk-status"` mais
# le seul method enregistré est PATCH → réponse 405.
@router.post("/anomalies/bulk-status", response_model=AnomalyBulkStatusOut)
def bulk_update_status(
    body: AnomalyBulkStatusIn,
    db: Session = Depends(get_db),
) -> AnomalyBulkStatusOut:
    """Met à jour le statut d'un lot d'anomalies. Utilisé par les boutons
    « Tout résoudre / Tout rejeter » de la vue Rédacteur."""
    if body.status not in _ALLOWED_STATUSES:
        raise AppError(
            "ANOMALY_STATUS_INVALID",
            f"Statut invalide. Valeurs autorisées : {sorted(_ALLOWED_STATUSES)}",
            status_code=400,
            detail={"status": body.status},
        )
    if not body.ids:
        return AnomalyBulkStatusOut(updated=0, status=body.status)

    now = datetime.now(timezone.utc) if body.status in ("fixed", "rejected") else None
    rows = list(db.scalars(select(Anomaly).where(Anomaly.id.in_(body.ids))))
    for a in rows:
        a.status = body.status
        a.resolved_at = now
    db.commit()
    return AnomalyBulkStatusOut(updated=len(rows), status=body.status)


@router.patch("/anomalies/{anomaly_id}", response_model=AnomalyOut)
def update_anomaly_status(
    anomaly_id: uuid.UUID,
    body: AnomalyStatusIn,
    db: Session = Depends(get_db),
) -> Anomaly:
    a = db.get(Anomaly, anomaly_id)
    if a is None:
        raise AppError("ANOMALY_NOT_FOUND", "Anomalie introuvable",
                       status_code=404, detail={"id": str(anomaly_id)})
    if body.status not in _ALLOWED_STATUSES:
        raise AppError(
            "ANOMALY_STATUS_INVALID",
            f"Statut invalide. Valeurs autorisées : {sorted(_ALLOWED_STATUSES)}",
            status_code=400,
            detail={"status": body.status},
        )
    a.status = body.status
    a.resolved_at = datetime.now(timezone.utc) if body.status in ("fixed", "rejected") else None
    db.commit()
    db.refresh(a)
    return a


@router.get("/projects/{project_id}/anomalies/export.csv")
def export_anomalies_csv(project_id: uuid.UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Projet introuvable",
                       status_code=404, detail={"id": str(project_id)})

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([
        "id", "type", "severity", "status", "message", "suggestion",
        "location", "created_at", "resolved_at",
    ])
    for a in project.anomalies:
        writer.writerow([
            str(a.id),
            a.type,
            a.severity,
            a.status,
            (a.message or "").replace("\n", " "),
            (a.suggestion or "").replace("\n", " "),
            a.location or "",
            a.created_at.isoformat() if a.created_at else "",
            a.resolved_at.isoformat() if a.resolved_at else "",
        ])
    buf.seek(0)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project.name)
    filename = f"anomalies_{safe_name}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.read()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
