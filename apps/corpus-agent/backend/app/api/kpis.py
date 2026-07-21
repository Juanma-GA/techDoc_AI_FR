"""KPIs Manager — single project ou multi-projets/global."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.rules import ANOMALY_TYPES
from app.db.models import AnalysisRun, Anomaly, Project
from app.db.session import get_db
from app.schemas import KpiOut


router = APIRouter(tags=["kpis"])


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def compute_kpis(db: Session, projects: list[Project]) -> KpiOut:
    """Agrège les KPIs sur la liste de projets (vide → KPIs nuls)."""
    if not projects:
        return KpiOut(
            open_anomalies=0, anomalies_by_severity={}, anomalies_by_type={},
            anomalies_by_category={},
            anomalies_by_status={}, resolution_rate=0.0,
            anomalies_by_confidence={},
            anomalies_over_time=[], top_files=[], top_rules=[],
            avg_age_days=0.0, avg_resolution_days=0.0,
            files_total=0, files_with_anomalies=0,
        )

    project_ids = [p.id for p in projects]

    anomalies: list[Anomaly] = list(db.scalars(
        select(Anomaly).where(Anomaly.project_id.in_(project_ids))
    ))
    # `dmc_missing` = écart de couverture du référentiel, traité dans la carte
    # « Couverture du référentiel » (% + matrice). On l'exclut de tout ce qui
    # est étiqueté « Anomalies » (compteur ouvert, graphe sévérité, graphe type,
    # confiance, âge moyen) pour éviter que le KPI principal soit dominé par des
    # FTM pas encore livrées.
    quality_anomalies = [a for a in anomalies if a.type != "dmc_missing"]
    open_a = [a for a in quality_anomalies if a.status == "open"]
    by_sev = Counter(a.severity for a in open_a)
    # Niveau de confiance IA des anomalies ouvertes — 3 cles toujours presentes.
    conf_counts = Counter((a.confidence or "elevee") for a in open_a)
    by_conf = {c: conf_counts.get(c, 0) for c in ("elevee", "moyenne", "faible")}
    # by_type : meme population que by_sev (anomalies qualite ouvertes) — les
    # deux graphes a barres somment ainsi au meme total que `open_anomalies`.
    by_type = Counter(a.type for a in open_a)
    # by_category : regroupement metier par « Sujet » de la regle checklist. En
    # mode checklist-only, c'est LA dimension utile (le type est toujours
    # `personnalisee`). Anomalies sans categorie regroupees sous « Sans sujet ».
    by_category = Counter((a.category or "Sans sujet") for a in open_a)

    # Repartition sur le workflow d'etat des tickets — toujours les 4 cles
    # presentes (0 explicite) pour un rendu stable cote dashboard.
    status_counts = Counter(a.status for a in quality_anomalies)
    by_status = {s: status_counts.get(s, 0) for s in ("open", "acknowledged", "fixed", "rejected")}
    total_quality = len(quality_anomalies)
    resolution_rate = round(100.0 * by_status["fixed"] / total_quality, 1) if total_quality else 0.0

    now = datetime.now(timezone.utc)
    ages = [(now - _aware(a.created_at)).total_seconds() / 86400.0 for a in open_a if a.created_at]
    avg_age = round(sum(ages) / len(ages), 2) if ages else 0.0

    durations = [
        (_aware(a.resolved_at) - _aware(a.created_at)).total_seconds() / 86400.0
        for a in quality_anomalies
        if a.status == "fixed" and a.resolved_at and a.created_at
    ]
    avg_res = round(sum(durations) / len(durations), 2) if durations else 0.0

    file_counts: Counter[str] = Counter()
    for a in quality_anomalies:
        if a.file_version and a.file_version.filename:
            file_counts[a.file_version.filename] += 1
    top_files = [{"filename": f, "count": c} for f, c in file_counts.most_common(5)]

    # Top « règles » = familles de contrôle (type d'anomalie) les plus émettrices.
    rule_counts: Counter[str] = Counter(a.type for a in quality_anomalies)
    top_rules = [{"rule": r, "count": c} for r, c in rule_counts.most_common(5)]

    runs = list(db.scalars(
        select(AnalysisRun)
        .where(AnalysisRun.project_id.in_(project_ids), AnalysisRun.status == "completed")
        .order_by(AnalysisRun.started_at.asc())
    ))
    over_time = []
    for r in runs:
        try:
            summary = json.loads(r.summary or "{}")
        except json.JSONDecodeError:
            summary = {}
        total = sum(
            v for k, v in summary.items()
            if k in ANOMALY_TYPES and isinstance(v, int)
        )
        over_time.append({
            "run_id": str(r.id),
            "started_at": r.started_at.isoformat() if r.started_at else "",
            "total": total,
            **{k: int(summary.get(k, 0) or 0) for k in ANOMALY_TYPES},
        })

    files_total = sum(len(p.files) for p in projects)
    files_with_anom = len({a.file_version.file_id for a in anomalies if a.file_version and a.file_version.file_id})

    return KpiOut(
        open_anomalies=len(open_a),
        anomalies_by_severity=dict(by_sev),
        anomalies_by_type=dict(by_type),
        anomalies_by_category=dict(by_category),
        anomalies_by_status=by_status,
        resolution_rate=resolution_rate,
        anomalies_by_confidence=by_conf,
        anomalies_over_time=over_time,
        top_files=top_files,
        top_rules=top_rules,
        avg_age_days=avg_age,
        avg_resolution_days=avg_res,
        files_total=files_total,
        files_with_anomalies=files_with_anom,
    )


@router.get("/projects/{project_id}/kpis", response_model=KpiOut)
def get_kpis_single(project_id: uuid.UUID, db: Session = Depends(get_db)) -> KpiOut:
    project = db.get(Project, project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Projet introuvable",
                       status_code=404, detail={"id": str(project_id)})
    return compute_kpis(db, [project])


@router.get("/kpis", response_model=KpiOut)
def get_kpis_scope(
    project_ids: Optional[str] = Query(default=None, description="CSV d'UUIDs ; vide ou absent = tous les projets"),
    db: Session = Depends(get_db),
) -> KpiOut:
    """Multi-scope : `project_ids` vide → tous les projets ; CSV d'UUIDs → subset."""
    if project_ids:
        try:
            ids = [uuid.UUID(s.strip()) for s in project_ids.split(",") if s.strip()]
        except ValueError as e:
            raise AppError("PROJECT_IDS_INVALID", f"UUID invalide : {e}", status_code=422) from e
        projects = list(db.scalars(select(Project).where(Project.id.in_(ids))))
    else:
        projects = list(db.scalars(select(Project)))
    return compute_kpis(db, projects)
