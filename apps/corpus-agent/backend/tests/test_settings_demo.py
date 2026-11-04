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


def test_checklists_are_isolated_by_mode(client, monkeypatch, tmp_path) -> None:
    from app.core import rules

    monkeypatch.setattr(rules, "_RULES_FILE", tmp_path / "rules.json")
    normal = {"id": "normal", "label": "Normal fixture", "consigne": "Normal check", "validated": True}
    demo = {"id": "demo", "label": "Demo fixture", "consigne": "Demo check", "validated": True}
    client.post("/api/v1/settings", json={"demo_enabled": False}).raise_for_status()
    client.put("/api/v1/settings/rules/sparse", json={"regles_personnalisees": [normal]}).raise_for_status()
    client.post("/api/v1/settings", json={"demo_enabled": True}).raise_for_status()
    assert client.get("/api/v1/settings/rules").json()["rules"]["regles_personnalisees"] == []
    client.put("/api/v1/settings/rules/sparse", json={"regles_personnalisees": [demo]}).raise_for_status()
    client.post("/api/v1/settings", json={"demo_enabled": False}).raise_for_status()
    assert client.get("/api/v1/settings/rules").json()["rules"]["regles_personnalisees"] == [normal]
    client.delete("/api/v1/settings/rules").raise_for_status()
    client.post("/api/v1/settings", json={"demo_enabled": True}).raise_for_status()
    assert client.get("/api/v1/settings/rules").json()["rules"]["regles_personnalisees"] == [demo]
    client.post("/api/v1/settings", json={"demo_enabled": False}).raise_for_status()


def test_normal_mode_hides_leftover_demo_project(client) -> None:
    from app.core.demo_mode import set_demo_enabled
    from app.db.session import SessionLocal

    client.post("/api/v1/settings", json={"demo_enabled": True}).raise_for_status()
    demo_id = client.get("/api/v1/projects").json()[0]["id"]
    with SessionLocal() as db:
        set_demo_enabled(db, False)
    assert demo_id not in [project["id"] for project in client.get("/api/v1/projects").json()]
    assert client.get(f"/api/v1/projects/{demo_id}").status_code == 404
    assert client.get("/api/v1/health/connectivity").json()["sources"]["documents"]["configured"] == 0
    client.post("/api/v1/settings", json={"demo_enabled": False}).raise_for_status()


def test_renamed_generated_project_is_still_demo_only(client) -> None:
    from app.core.demo_mode import set_demo_enabled
    from app.db.models import Project
    from app.db.session import SessionLocal

    client.post("/api/v1/settings", json={"demo_enabled": True}).raise_for_status()
    demo_id = client.get("/api/v1/projects").json()[0]["id"]
    with SessionLocal() as db:
        import uuid

        project = db.get(Project, uuid.UUID(demo_id))
        project.name = "Fiches de maintenance"
        db.commit()
        set_demo_enabled(db, False)
    assert client.get(f"/api/v1/projects/{demo_id}").status_code == 404
    assert client.get("/api/v1/kpis").json()["files_total"] == 0
    stats = client.get("/api/v1/admin/stats").json()
    assert stats["projects"] == stats["files"] == stats["anomalies"] == stats["analysis_runs"] == 0
    assert stats["storage_bytes"] == 0
    client.post("/api/v1/settings", json={"demo_enabled": True}).raise_for_status()
    assert client.get("/api/v1/projects").json()[0]["id"] == demo_id
    assert client.get("/api/v1/admin/stats").json()["files"] == 3
    client.post("/api/v1/settings", json={"demo_enabled": False}).raise_for_status()
    assert client.get(f"/api/v1/projects/{demo_id}").status_code == 404


def test_demo_folder_is_restored_only_in_demo_mode(client, tmp_path) -> None:
    folder = tmp_path / "synthetic-demo-folder"
    folder.mkdir()
    client.post("/api/v1/settings", json={"demo_enabled": True}).raise_for_status()
    project_id = client.get("/api/v1/projects").json()[0]["id"]
    response = client.post(
        f"/api/v1/projects/{project_id}/files/sync-folder", json={"path": str(folder), "only": []},
    )
    response.raise_for_status()
    client.post("/api/v1/settings", json={"demo_enabled": False}).raise_for_status()
    assert client.get("/api/v1/health/connectivity").json()["sources"]["folder"]["configured"] == 0
    client.post("/api/v1/settings", json={"demo_enabled": True}).raise_for_status()
    assert client.get("/api/v1/health/connectivity").json()["sources"]["folder"]["available"] == 1
    client.post("/api/v1/settings", json={"demo_enabled": False}).raise_for_status()


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


def test_demo_shows_one_project_and_keeps_normal_projects(client) -> None:
    from app.core.demo_seed import DEMO_PROJECT_NAME

    client.post("/api/v1/settings", json={"demo_enabled": False})
    normal = client.post("/api/v1/projects", json={"name": "Synthetic normal project"}).json()
    normal_id = normal["id"]
    upload = client.post(
        f"/api/v1/projects/{normal_id}/files",
        files={"files": ("normal.txt", b"Synthetic normal document.", "text/plain")},
    )
    assert upload.status_code == 200

    client.post("/api/v1/settings", json={"demo_enabled": True})
    projects = client.get("/api/v1/projects").json()
    assert len(projects) == 1
    assert projects[0]["name"] == DEMO_PROJECT_NAME
    assert projects[0]["id"] != normal_id
    assert client.get("/api/v1/kpis").json()["files_total"] == 3
    assert client.get(f"/api/v1/projects/{normal_id}").status_code == 404
    assert client.get(f"/api/v1/projects/{normal_id}/kpis").status_code == 404
    assert client.get("/api/v1/kpis", params={"project_ids": normal_id}).json()["files_total"] == 0
    response = client.post("/api/v1/projects", json={"name": "Second demo project"})
    assert response.status_code == 409
    assert response.json()["code"] == "DEMO_SINGLE_PROJECT"
    demo_id = projects[0]["id"]
    assert client.put(f"/api/v1/projects/{demo_id}", json={"name": "Renamed demo"}).status_code == 409
    assert client.delete(f"/api/v1/projects/{demo_id}").status_code == 409

    client.post("/api/v1/settings", json={"demo_enabled": False})
    assert normal_id in [project["id"] for project in client.get("/api/v1/projects").json()]
    assert client.get(f"/api/v1/projects/{normal_id}/files").json()[0]["current_name"] == "normal.txt"
    client.delete(f"/api/v1/projects/{normal_id}")


def test_demo_chat_scope_is_limited_to_the_demo_project(client) -> None:
    import json

    from app.api.chat import _resolve_projects
    from app.db.models import ChatSession, Project
    from app.db.session import SessionLocal

    client.post("/api/v1/settings", json={"demo_enabled": False})
    with SessionLocal() as db:
        normal = Project(name="Synthetic chat project")
        db.add(normal)
        db.commit()
        normal_id = normal.id

    client.post("/api/v1/settings", json={"demo_enabled": True})
    demo_id = client.get("/api/v1/projects").json()[0]["id"]
    with SessionLocal() as db:
        projects = _resolve_projects(db, [])
        assert [str(project.id) for project in projects] == [demo_id]
        for primary, scope in (
            (projects[0].id, [demo_id]),
            (normal_id, [str(normal_id)]),
            (projects[0].id, [demo_id, str(normal_id)]),
            (None, []),
        ):
            db.add(ChatSession(
                project_id=primary,
                scope_project_ids=json.dumps(scope),
                title="Synthetic conversation",
            ))
        db.commit()

    sessions = client.get("/api/v1/chat/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["scope_project_ids"] == [demo_id]
    client.post("/api/v1/settings", json={"demo_enabled": False})
    client.delete(f"/api/v1/projects/{normal_id}")


def test_demo_refresh_preserves_project_after_additional_analysis(client) -> None:
    client.post("/api/v1/settings", json={"demo_enabled": True})
    demo_id = client.get("/api/v1/projects").json()[0]["id"]
    result = client.post(f"/api/v1/projects/{demo_id}/analysis/run")
    assert result.status_code == 200
    client.get("/api/v1/settings")
    assert client.get("/api/v1/projects").json()[0]["id"] == demo_id
    assert len(client.get(f"/api/v1/projects/{demo_id}/analysis/runs").json()) == 5
    client.post("/api/v1/settings", json={"demo_enabled": False})
