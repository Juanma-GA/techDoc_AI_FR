"""Feedback sur rejet d'anomalie (motif du relecteur)."""

from __future__ import annotations

import uuid as _uuid

import pytest
from fastapi.testclient import TestClient

from app.db.models import Anomaly, Project
from app.db.session import Base, SessionLocal, engine
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(create_app())


def _make_anomaly() -> str:
    db = SessionLocal()
    try:
        p = Project(name=f"P-{_uuid.uuid4().hex[:8]}")
        db.add(p)
        db.flush()
        a = Anomaly(
            project_id=p.id, type="personnalisee", category="Sécurité",
            severity="high", message="écart", suggestion="", location="", status="open",
        )
        db.add(a)
        db.commit()
        return str(a.id)
    finally:
        db.close()


def test_reject_with_feedback_persists(client: TestClient) -> None:
    aid = _make_anomaly()
    resp = client.patch(f"/api/v1/anomalies/{aid}", json={"status": "rejected", "feedback": "faux positif"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["feedback"] == "faux positif"


def test_status_without_feedback_keeps_existing(client: TestClient) -> None:
    """Un changement de statut sans `feedback` ne l'ecrase pas."""
    aid = _make_anomaly()
    client.patch(f"/api/v1/anomalies/{aid}", json={"status": "rejected", "feedback": "hors perimetre"})
    # Re-passage a open sans feedback -> le motif reste.
    resp = client.patch(f"/api/v1/anomalies/{aid}", json={"status": "open"})
    assert resp.status_code == 200
    assert resp.json()["feedback"] == "hors perimetre"


def test_bulk_reject_with_feedback(client: TestClient) -> None:
    a1, a2 = _make_anomaly(), _make_anomaly()
    resp = client.post(
        "/api/v1/anomalies/bulk-status",
        json={"ids": [a1, a2], "status": "rejected", "feedback": "lot rejete"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2
    db = SessionLocal()
    try:
        for aid in (a1, a2):
            row = db.get(Anomaly, _uuid.UUID(aid))
            assert row is not None and row.feedback == "lot rejete"
    finally:
        db.close()
