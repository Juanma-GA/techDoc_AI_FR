"""Feedback sur rejet d'anomalie (motif du relecteur)."""

from __future__ import annotations

import uuid as _uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.anomalies import router as anomalies_router
from app.db.models import Anomaly, Project
from app.db.session import Base, SessionLocal, engine, get_db


def _test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(anomalies_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _test_db
    return TestClient(app)


def _make_anomaly() -> str:
    db = SessionLocal()
    try:
        p = Project(name=f"P-{_uuid.uuid4().hex[:8]}")
        db.add(p)
        db.flush()
        a = Anomaly(
            project_id=p.id, type="personnalisee", category="Sécurité",
            severity="high", message="écart", suggestion="", evidence="preuve synthétique",
            location="", status="open",
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
    assert body["evidence"] == "preuve synthétique"
    assert body["run_id"] is None


def test_anomaly_csv_exports_source_evidence(client: TestClient) -> None:
    anomaly_id = _make_anomaly()
    with SessionLocal() as db:
        anomaly = db.get(Anomaly, _uuid.UUID(anomaly_id))
        assert anomaly is not None
        project_id = str(anomaly.project_id)

    response = client.get(f"/api/v1/projects/{project_id}/anomalies/export.csv")

    assert response.status_code == 200
    assert "file_version_id" in response.text.splitlines()[0]
    assert "run_id" in response.text.splitlines()[0]
    assert "evidence" in response.text.splitlines()[0]
    assert "preuve synthétique" in response.text


def test_status_without_feedback_keeps_existing(client: TestClient) -> None:
    """Un changement de statut sans `feedback` ne l'ecrase pas."""
    aid = _make_anomaly()
    client.patch(f"/api/v1/anomalies/{aid}", json={"status": "rejected", "feedback": "hors perimetre"})
    # Re-passage a open sans feedback -> le motif reste.
    resp = client.patch(f"/api/v1/anomalies/{aid}", json={"status": "open"})
    assert resp.status_code == 200
    assert resp.json()["feedback"] == "hors perimetre"


def test_chat_context_surfaces_rejection_feedback(client: TestClient) -> None:
    """Le contexte chat expose le motif de rejet + le récap « rejets par sujet »
    (pour interroger les faux positifs et réviser la checklist)."""
    from unittest.mock import MagicMock

    from app.core.chat_engine import build_context_messages

    db = SessionLocal()
    try:
        p = Project(name=f"P-{_uuid.uuid4().hex[:8]}")
        db.add(p)
        db.flush()
        a = Anomaly(
            project_id=p.id, type="personnalisee", category="Script",
            severity="high", message="écart script", suggestion="", location="",
            status="rejected", feedback="faux positif : script hors référentiel toléré",
        )
        db.add(a)
        db.commit()
        mistral = MagicMock()
        mistral.embed.side_effect = Exception("pas d'embeddings en test")
        messages, _ = build_context_messages(db, [p], "quels sujets rejeter ?", mistral)
        content = messages[-1]["content"]
        assert "motif du relecteur : faux positif" in content
        assert "Rejets par sujet" in content
        assert "Script=1" in content
    finally:
        db.close()


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
