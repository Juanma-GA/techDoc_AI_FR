"""Synthèse des rejets : GET /projects/{id}/anomalies/rejections-summary.

Vérifie l'agrégat déterministe (par sujet + motifs) et le fallback gracieux de
la synthèse IA (pas de clé Mistral en test -> synthese vide, jamais d'appel
réseau ni de 5xx)."""

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


def _project_with_rejections() -> str:
    db = SessionLocal()
    try:
        p = Project(name=f"P-{_uuid.uuid4().hex[:8]}")
        db.add(p)
        db.flush()
        db.add_all([
            Anomaly(project_id=p.id, type="personnalisee", category="Sécurité",
                    severity="high", message="ecart 1", status="rejected",
                    feedback="faux positif"),
            Anomaly(project_id=p.id, type="personnalisee", category="Sécurité",
                    severity="medium", message="ecart 2", status="rejected",
                    feedback="hors perimetre"),
            Anomaly(project_id=p.id, type="personnalisee", category="Script",
                    severity="low", message="ecart 3", status="rejected", feedback=""),
            # une anomalie OUVERTE ne doit PAS apparaitre dans la synthese des rejets
            Anomaly(project_id=p.id, type="personnalisee", category="Script",
                    severity="low", message="ouverte", status="open"),
        ])
        db.commit()
        return str(p.id)
    finally:
        db.close()


def test_rejections_summary_aggregates(client: TestClient) -> None:
    pid = _project_with_rejections()
    r = client.get(f"/api/v1/projects/{pid}/anomalies/rejections-summary?synthesize=false")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["total"] == 3  # 3 rejetees (l'ouverte est exclue)
    by_cat = {c["category"]: c["count"] for c in body["by_category"]}
    assert by_cat == {"Sécurité": 2, "Script": 1}
    # tri par count decroissant
    assert body["by_category"][0]["category"] == "Sécurité"

    assert len(body["items"]) == 3
    motifs = {i["feedback"] for i in body["items"]}
    assert "faux positif" in motifs and "hors perimetre" in motifs
    assert all(i["file"] for i in body["items"])  # "fichier inconnu" a defaut

    # synthesize=false -> pas de synthese IA
    assert body["synthese"] == ""
    assert body["llm_used"] is False


def test_rejections_summary_ai_graceful_without_key(client: TestClient) -> None:
    """synthesize=true mais aucune clé Mistral -> pas d'appel réseau, fallback
    sur l'agrégat déterministe (synthese vide, llm_used false)."""
    pid = _project_with_rejections()
    r = client.get(f"/api/v1/projects/{pid}/anomalies/rejections-summary?synthesize=true")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["synthese"] == ""
    assert body["llm_used"] is False


def test_rejections_summary_empty_project(client: TestClient) -> None:
    db = SessionLocal()
    try:
        p = Project(name="vide")
        db.add(p)
        db.commit()
        pid = str(p.id)
    finally:
        db.close()
    r = client.get(f"/api/v1/projects/{pid}/anomalies/rejections-summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["by_category"] == []
    assert body["items"] == []


def test_rejections_summary_project_not_found(client: TestClient) -> None:
    r = client.get(f"/api/v1/projects/{_uuid.uuid4()}/anomalies/rejections-summary")
    assert r.status_code == 404
    assert r.json()["code"] == "PROJECT_NOT_FOUND"
