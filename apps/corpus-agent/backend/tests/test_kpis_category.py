"""KPIs regroupés par catégorie (Sujet de la règle checklist).

Vérifie qu'en mode checklist-only, `compute_kpis` agrège les anomalies ouvertes
par `category` (et non plus par un type figé).
"""

from __future__ import annotations

import pytest

from app.api.kpis import compute_kpis
from app.db.models import Anomaly, Project
from app.db.session import Base, SessionLocal, engine


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def _anomaly(project_id, category: str, status: str = "open") -> Anomaly:
    return Anomaly(
        project_id=project_id,
        type="personnalisee",
        category=category,
        severity="medium",
        message=f"[{category}] écart",
        suggestion="",
        location="",
        status=status,
    )


def test_kpis_group_by_category(db) -> None:
    project = Project(name="P")
    db.add(project)
    db.flush()
    db.add_all([
        _anomaly(project.id, "Sécurité"),
        _anomaly(project.id, "Sécurité"),
        _anomaly(project.id, "Terminologie"),
        _anomaly(project.id, "Terminologie", status="fixed"),  # non ouverte -> exclue
    ])
    db.commit()

    kpi = compute_kpis(db, [project])
    assert kpi.anomalies_by_category == {"Sécurité": 2, "Terminologie": 1}
    # Le type reste unique (checklist-only) — la catégorie porte le regroupement.
    assert kpi.anomalies_by_type == {"personnalisee": 3}


def test_kpis_category_fallback_label(db) -> None:
    """Une anomalie sans catégorie est regroupée sous « Sans sujet »."""
    project = Project(name="P2")
    db.add(project)
    db.flush()
    db.add(_anomaly(project.id, ""))
    db.commit()

    kpi = compute_kpis(db, [project])
    assert kpi.anomalies_by_category == {"Sans sujet": 1}


def test_over_time_stacked_by_category(db) -> None:
    """Le graphe temporel expose, par run, la répartition par catégorie."""
    from datetime import datetime, timezone

    from app.db.models import AnalysisRun

    project = Project(name="P3")
    db.add(project)
    db.flush()
    run = AnalysisRun(
        project_id=project.id, status="completed",
        started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
        summary="{}",
    )
    db.add(run)
    db.flush()
    for cat in ("Sécurité", "Sécurité", "Script"):
        a = _anomaly(project.id, cat)
        a.run_id = run.id
        db.add(a)
    db.commit()

    kpi = compute_kpis(db, [project])
    assert len(kpi.anomalies_over_time) == 1
    point = kpi.anomalies_over_time[0]
    assert point["total"] == 3
    assert point["categories"] == {"Sécurité": 2, "Script": 1}
