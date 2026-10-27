from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.session import Base, engine
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    Base.metadata.create_all(bind=engine)
    return TestClient(create_app())


def test_demo_mode_defaults_to_normal(client) -> None:
    response = client.get("/api/v1/settings")

    assert response.status_code == 200
    assert response.json() == {"demo_enabled": False}


def test_demo_mode_setting_persists(client) -> None:
    response = client.post("/api/v1/settings", json={"demo_enabled": True})

    assert response.status_code == 200
    assert response.json() == {"demo_enabled": True}
    assert client.get("/api/v1/settings").json() == {"demo_enabled": True}

    client.post("/api/v1/settings", json={"demo_enabled": False})
    assert client.get("/api/v1/settings").json() == {"demo_enabled": False}


def test_demo_mode_seeds_and_removes_demo_project(client) -> None:
    client.post("/api/v1/settings", json={"demo_enabled": True})
    client.post("/api/v1/settings", json={"demo_enabled": True})

    projects = client.get("/api/v1/projects").json()
    demo = [p for p in projects if p["name"].startswith("Projet démo")]
    assert len(demo) == 1
    files = client.get(f"/api/v1/projects/{demo[0]['id']}/files").json()
    assert len(files) == 3
    assert all(f["current_name"].endswith(".xlsx") for f in files)

    from openpyxl import load_workbook

    from app.parsers import parse_any

    from app.db.session import SessionLocal
    from app.db.models import FileVersion

    with SessionLocal() as db:
        version = db.query(FileVersion).filter(FileVersion.filename == files[0]["current_name"]).first()
        parsed = parse_any(version.storage_path)
        wb = load_workbook(version.storage_path)
    assert len(parsed["sections"]) >= 4
    assert len(wb.sheetnames) >= 4

    client.post("/api/v1/settings", json={"demo_enabled": False})
    assert not [p for p in client.get("/api/v1/projects").json() if p["name"].startswith("Projet démo")]


def test_demo_project_feeds_dashboard_kpis(client) -> None:
    client.post("/api/v1/settings", json={"demo_enabled": True})
    kpis = client.get("/api/v1/kpis").json()

    assert kpis["open_anomalies"] > 0
    assert kpis["resolution_rate"] > 0
    assert kpis["files_total"] == 3
    totals = [run["total"] for run in kpis["anomalies_over_time"]]
    assert len(totals) == 4
    assert totals == sorted(totals, reverse=True)
    assert totals[0] > totals[-1]
    assert len(kpis["anomalies_by_category"]) >= 3
    assert kpis["top_files"]

    client.post("/api/v1/settings", json={"demo_enabled": False})
    assert client.get("/api/v1/kpis").json()["open_anomalies"] == 0


def test_stale_demo_project_is_regenerated_on_load(client) -> None:
    from sqlalchemy import delete

    from app.db.models import AnalysisRun
    from app.db.session import SessionLocal

    client.post("/api/v1/settings", json={"demo_enabled": True})
    with SessionLocal() as db:
        run = db.query(AnalysisRun).order_by(AnalysisRun.started_at).first()
        db.execute(delete(AnalysisRun).where(AnalysisRun.id == run.id))
        db.commit()
    assert len(client.get("/api/v1/kpis").json()["anomalies_over_time"]) < 4

    assert client.get("/api/v1/settings").json()["demo_enabled"] is True
    totals = [r["total"] for r in client.get("/api/v1/kpis").json()["anomalies_over_time"]]
    assert totals == sorted(totals, reverse=True)
    assert len(totals) == 4


def test_demo_data_is_attached_to_demo_project_only(client) -> None:
    from app.core.demo_seed import DEMO_PROJECT_NAME
    from app.db.models import AnalysisRun, Anomaly, File, FileVersion, Project
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        # Projet utilisateur avec des fichiers homonymes de ceux de la demo
        other = Project(name="Projet utilisateur")
        db.add(other)
        db.flush()
        for name in ("FTM-DEMO-32-10-01.xlsx", "FTM-DEMO-21-30-02.xlsx", "FTM-DEMO-24-50-03.xlsx"):
            f = File(project_id=other.id, current_name=name)
            db.add(f)
            db.flush()
            db.add(FileVersion(file_id=f.id, filename=name, storage_path="x", sha256="0" * 64))
        db.commit()

    client.post("/api/v1/settings", json={"demo_enabled": True})

    with SessionLocal() as db:
        demo = db.query(Project).filter(Project.name == DEMO_PROJECT_NAME).one()
        anomalies = db.query(Anomaly).filter(Anomaly.project_id == demo.id).all()
        assert anomalies
        for a in anomalies:
            assert a.file_version.file.project_id == demo.id
            assert db.get(AnalysisRun, a.run_id).project_id == demo.id
        assert db.query(Anomaly).filter(Anomaly.project_id != demo.id).count() == 0
        assert db.query(File).filter(File.project_id == demo.id).count() == 3


def test_demo_mode_survives_admin_reset(client) -> None:
    client.post("/api/v1/settings", json={"demo_enabled": True})
    client.post("/api/v1/admin/reset", json={"scope": "all"})

    assert client.get("/api/v1/settings").json() == {"demo_enabled": True}
    client.post("/api/v1/settings", json={"demo_enabled": False})
