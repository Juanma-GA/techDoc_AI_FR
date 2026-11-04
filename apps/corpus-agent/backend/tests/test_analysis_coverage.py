from __future__ import annotations

import json
import uuid
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import analysis
from app.checks import custom_rules
from app.db.models import Anomaly, File, FileVersion, Project
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
    app.include_router(analysis.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _test_db
    return TestClient(app)


def _project_with_files(names: list[str]) -> str:
    with SessionLocal() as db:
        project = Project(name=f"Coverage-{uuid.uuid4().hex[:8]}")
        db.add(project)
        db.flush()
        for name in names:
            file = File(project_id=project.id, current_name=name)
            db.add(file)
            db.flush()
            db.add(
                FileVersion(
                    file_id=file.id,
                    filename=name,
                    storage_path=f"synthetic/{name}",
                    sha256=uuid.uuid4().hex * 2,
                    extracted_text="",
                )
            )
        db.commit()
        return str(project.id)


def _enable_evaluation(
    monkeypatch: pytest.MonkeyPatch,
    *,
    parse: Callable[[str], dict[str, str]],
    fail_llm: bool = False,
) -> None:
    monkeypatch.setattr(
        custom_rules,
        "load_rules",
        lambda: {
            "regles_personnalisees": [
                {"id": "r1", "label": "Completeness", "consigne": "Check required content"}
            ],
            "instructions_libres": "",
        },
    )
    monkeypatch.setattr(analysis, "parse_any", parse)
    monkeypatch.setattr(analysis, "index_file_version", lambda *_args: 1)

    class FakeMistral:
        chat_model = "synthetic-model"

        def chat_json(self, _messages):
            if fail_llm:
                raise RuntimeError("synthetic model failure")
            return {"anomalies": []}

    monkeypatch.setattr(
        analysis.MistralClient,
        "from_db",
        classmethod(lambda _cls, _db: FakeMistral()),
    )


def _run_summary(client: TestClient, project_id: str) -> dict:
    response = client.post(f"/api/v1/projects/{project_id}/analysis/run")
    assert response.status_code == 200, response.text
    return json.loads(response.json()["summary"])


def test_complete_analysis_reports_coverage_and_rule_evaluations(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _project_with_files(["one.txt", "two.txt"])
    _enable_evaluation(monkeypatch, parse=lambda _path: {"text": "synthetic document text"})

    summary = _run_summary(client, project_id)

    assert summary["verification_status"] == "verified"
    assert summary["files_in_project"] == 2
    assert summary["files_selected"] == 2
    assert summary["files_parsed"] == 2
    assert summary["files_with_text"] == 2
    assert summary["files_verified"] == 2
    assert summary["evaluation_calls"] == 2
    assert summary["evaluation_failures"] == 0
    assert summary["rules_evaluated"] == 2
    assert summary["rule_set_sha256"]
    assert summary["prompt_version"] == "custom-rules-v1"
    assert summary["llm_model"] == "synthetic-model"
    assert summary["indexed_chunks"] == 2


def test_parse_failure_makes_successful_partial_run_explicit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _project_with_files(["good.txt", "bad.txt"])

    def parse(path: str) -> dict[str, str]:
        if path.endswith("bad.txt"):
            raise ValueError("synthetic parse failure")
        return {"text": "synthetic readable text"}

    _enable_evaluation(monkeypatch, parse=parse)
    summary = _run_summary(client, project_id)

    assert summary["verification_status"] == "partial"
    assert summary["files_selected"] == 2
    assert summary["files_verified"] == 1
    assert summary["files_parse_failed"] == 1


def test_empty_extraction_is_not_reported_as_verified(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _project_with_files(["empty.txt"])
    _enable_evaluation(monkeypatch, parse=lambda _path: {"text": " \n "})

    summary = _run_summary(client, project_id)

    assert summary["verification_status"] == "not_verified"
    assert summary["files_empty"] == 1
    assert summary["files_verified"] == 0
    assert summary["evaluation_calls"] == 0


def test_model_call_failure_is_counted_and_not_reported_as_verified(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _project_with_files(["one.txt"])
    _enable_evaluation(
        monkeypatch,
        parse=lambda _path: {"text": "synthetic readable text"},
        fail_llm=True,
    )

    summary = _run_summary(client, project_id)

    assert summary["verification_status"] == "not_verified"
    assert summary["evaluation_calls"] == 1
    assert summary["evaluation_failures"] == 1
    assert summary["rules_evaluated"] == 0


def test_unavailable_evaluation_preserves_existing_findings(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _project_with_files(["one.txt"])
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).one()
        version = db.query(FileVersion).filter(FileVersion.file_id == project.files[0].id).one()
        existing = Anomaly(
            project_id=project.id,
            file_version_id=version.id,
            type="personnalisee",
            category="Completeness",
            severity="high",
            message="Existing synthetic finding",
            suggestion="",
            evidence="Previously verified source text",
            location="",
            status="open",
        )
        db.add(existing)
        db.commit()
        existing_id = existing.id

    def unavailable(_cls, _db):
        raise analysis.MistralError("synthetic API key missing")

    monkeypatch.setattr(analysis.MistralClient, "from_db", classmethod(unavailable))
    monkeypatch.setattr(analysis, "parse_any", lambda _path: {"text": "synthetic readable text"})
    summary = _run_summary(client, project_id)

    assert summary["verification_status"] == "not_verified"
    with SessionLocal() as db:
        assert db.get(Anomaly, existing_id) is not None
