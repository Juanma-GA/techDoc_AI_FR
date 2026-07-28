"""Re-analyse : purge anti-accumulation + memoire des rejets (capitalisation).

Un check factice (independant de Mistral) produit toujours le meme ecart, ce qui
permet de tester la logique de `run_analysis` : un re-run ne duplique pas, et un
ecart deja rejete par le relecteur n'est pas re-signale.
"""

from __future__ import annotations

import uuid as _uuid

import pytest
from fastapi.testclient import TestClient

from app.db.models import Project
from app.db.session import Base, SessionLocal, engine
from app.main import create_app


def _fake_check(db, project, run_id, mistral, only_file_ids=None):  # type: ignore[no-untyped-def]
    from app.checks.ftm_doc import make_anomaly

    a = make_anomaly(
        project, None, run_id, "personnalisee", "medium",
        "[Script] ecart detecte", "", "le passage fautif", category="Script",
    )
    db.add(a)
    return [a]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.api.analysis._CHECKS", (_fake_check,))
    return TestClient(create_app())


def _project() -> str:
    db = SessionLocal()
    try:
        p = Project(name=f"P-{_uuid.uuid4().hex[:8]}")
        db.add(p)
        db.commit()
        return str(p.id)
    finally:
        db.close()


def test_rerun_does_not_accumulate(client: TestClient) -> None:
    pid = _project()
    client.post(f"/api/v1/projects/{pid}/analysis/run")
    client.post(f"/api/v1/projects/{pid}/analysis/run")
    anoms = client.get(f"/api/v1/projects/{pid}/anomalies").json()
    # Sans purge on aurait 2 doublons ; avec purge, une seule anomalie.
    assert len(anoms) == 1


def test_rejected_not_reflagged(client: TestClient) -> None:
    pid = _project()
    client.post(f"/api/v1/projects/{pid}/analysis/run")
    anoms = client.get(f"/api/v1/projects/{pid}/anomalies").json()
    assert len(anoms) == 1
    aid = anoms[0]["id"]
    # Le relecteur rejette avec un motif.
    client.patch(f"/api/v1/anomalies/{aid}", json={"status": "rejected", "feedback": "faux positif"})
    # Re-analyse : l'ecart identique ne doit PAS revenir en « open ».
    client.post(f"/api/v1/projects/{pid}/analysis/run")
    anoms = client.get(f"/api/v1/projects/{pid}/anomalies").json()
    assert len(anoms) == 1
    assert anoms[0]["status"] == "rejected"
    assert anoms[0]["feedback"] == "faux positif"
