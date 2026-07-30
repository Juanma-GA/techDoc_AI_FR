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
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.mistral_client import MistralClient, get_llm_enabled
from app.db.models import Anomaly, Project
from app.db.session import get_db
from app.schemas import AnomalyBulkStatusIn, AnomalyBulkStatusOut, AnomalyOut, AnomalyStatusIn

import structlog

router = APIRouter(tags=["anomalies"])

logger = structlog.get_logger(__name__)


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
        if body.feedback is not None:
            a.feedback = body.feedback
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
    if body.feedback is not None:
        a.feedback = body.feedback
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
        "id", "type", "category", "severity", "status", "message", "suggestion",
        "feedback", "location", "created_at", "resolved_at",
    ])
    for a in project.anomalies:
        writer.writerow([
            str(a.id),
            a.type,
            a.category or "",
            a.severity,
            a.status,
            (a.message or "").replace("\n", " "),
            (a.suggestion or "").replace("\n", " "),
            (a.feedback or "").replace("\n", " "),
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


# ---- Synthèse des rejets --------------------------------------------------
# Agrégat exploitable des anomalies REJETÉES (faux positifs / hors périmètre)
# par sujet (category) + leurs motifs, avec une synthèse IA optionnelle qui
# dégage les motifs récurrents et les règles de checklist à affiner/retirer.
# La synthèse LLM est gardée par `get_llm_enabled` (fallback gracieux : sans
# clé / LLM OFF, on renvoie l'agrégat déterministe et `synthese=""`).


class RejectionCategoryCount(BaseModel):
    category: str
    count: int


class RejectionItem(BaseModel):
    id: uuid.UUID
    file: str
    category: str
    severity: str
    message: str
    feedback: str
    location: str


class RejectionsSummaryOut(BaseModel):
    total: int
    by_category: list[RejectionCategoryCount]
    items: list[RejectionItem]
    synthese: str = ""
    llm_used: bool = False


_SYNTHESE_MAX_MOTIFS = 40  # borne les motifs envoyes au LLM (cout/tokens)


def _file_of(a: Anomaly) -> str:
    if a.file_version and a.file_version.filename:
        return a.file_version.filename
    return "fichier inconnu"


def _synthesize_rejections(
    client: MistralClient,
    project_name: str,
    by_category: list[RejectionCategoryCount],
    rejected: list[Anomaly],
) -> str:
    """Génère un court paragraphe de synthèse des rejets via Mistral."""
    cats = ", ".join(f"{c.category or 'sans sujet'}={c.count}" for c in by_category) or "aucun"
    motifs: list[str] = []
    for a in rejected:
        motif = (a.feedback or "").strip()
        if motif:
            motifs.append(f"- [{a.category or 'sans sujet'}] {motif}")
        if len(motifs) >= _SYNTHESE_MAX_MOTIFS:
            break
    motifs_block = "\n".join(motifs) if motifs else "(aucun motif saisi)"

    system = (
        "Tu es un analyste qualité documentaire. On te fournit les anomalies "
        "REJETÉES par le relecteur (donc des faux positifs ou hors périmètre) "
        "d'un projet, agrégées par sujet (règle de checklist) et avec les motifs "
        "de rejet. Rédige une SYNTHÈSE COURTE (5 à 8 phrases, en français) qui : "
        "1) dégage les motifs de rejet récurrents ; 2) identifie les sujets "
        "(règles) qui génèrent le plus de faux positifs et mériteraient d'être "
        "affinés ou retirés ; 3) reste concrète et actionnable. Pas de liste à "
        "puces, un paragraphe."
    )
    user = (
        f"Projet : {project_name}\n"
        f"Rejets par sujet : {cats}\n\n"
        f"Motifs de rejet (échantillon) :\n{motifs_block}"
    )
    return client.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
    ).strip()


@router.get(
    "/projects/{project_id}/anomalies/rejections-summary",
    response_model=RejectionsSummaryOut,
)
def rejections_summary(
    project_id: uuid.UUID,
    synthesize: bool = Query(
        default=True,
        description="Générer le paragraphe de synthèse IA (gardé par l'interrupteur LLM).",
    ),
    db: Session = Depends(get_db),
) -> RejectionsSummaryOut:
    project = db.get(Project, project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Projet introuvable",
                       status_code=404, detail={"id": str(project_id)})

    rejected = list(
        db.scalars(
            select(Anomaly)
            .where(Anomaly.project_id == project_id, Anomaly.status == "rejected")
            .order_by(Anomaly.category, Anomaly.created_at.desc())
        )
    )

    counts: dict[str, int] = {}
    for a in rejected:
        key = a.category or ""
        counts[key] = counts.get(key, 0) + 1
    by_category = [
        RejectionCategoryCount(category=k, count=v)
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
    ]
    items = [
        RejectionItem(
            id=a.id,
            file=_file_of(a),
            category=a.category or "",
            severity=a.severity,
            message=a.message or "",
            feedback=a.feedback or "",
            location=a.location or "",
        )
        for a in rejected
    ]

    synthese = ""
    llm_used = False
    # Synthese IA optionnelle : uniquement s'il y a des rejets et que l'IA est
    # activee. `MistralClient.from_db` LEVE si aucune cle n'est configuree -> on
    # englobe la construction ET l'appel dans le meme try : tout echec LLM
    # (cle absente, reseau, JSON) retombe silencieusement sur l'agregat
    # deterministe (jamais de 5xx a cause de la synthese).
    if synthesize and rejected and get_llm_enabled(db):
        try:
            client = MistralClient.from_db(db)
            synthese = _synthesize_rejections(client, project.name, by_category, rejected)
            llm_used = bool(synthese)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rejections_synthese_failed", error=type(exc).__name__, message=str(exc))

    return RejectionsSummaryOut(
        total=len(rejected),
        by_category=by_category,
        items=items,
        synthese=synthese,
        llm_used=llm_used,
    )
