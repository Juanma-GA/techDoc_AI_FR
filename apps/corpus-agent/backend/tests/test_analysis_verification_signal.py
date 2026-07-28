"""Signal `llm_used` / `active_rules` dans le resume d'analyse.

Sans ce signal, une analyse ou rien n'a ete verifie (LLM indisponible, ou 0
regle personnalisee active) affichait le meme resultat "0 anomalie" qu'une
analyse authentiquement conforme -> faux vert cote UI (cf. checklist QA).
"""

from __future__ import annotations

import json
import uuid as _uuid

import pytest
from fastapi.testclient import TestClient

from app.checks import custom_rules
from app.core.mistral_client import set_llm_enabled
from app.db.models import Project
from app.db.session import Base, SessionLocal, engine
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
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


def _run_summary(client: TestClient, pid: str) -> dict:
    resp = client.post(f"/api/v1/projects/{pid}/analysis/run")
    assert resp.status_code == 200, resp.text
    return json.loads(resp.json()["summary"] or "{}")


def test_llm_used_false_when_llm_disabled(client: TestClient) -> None:
    pid = _project()
    db = SessionLocal()
    try:
        set_llm_enabled(db, False)
    finally:
        db.close()

    summary = _run_summary(client, pid)
    assert summary["llm_used"] is False
    # Pas de rules.json configure dans ce test -> 0 regle active par defaut.
    assert summary["active_rules"] == 0


def test_llm_used_false_when_no_api_key_configured(client: TestClient) -> None:
    # LLM active (defaut), mais aucune cle Mistral -> MistralClient.from_db
    # leve MistralError, capturee par run_analysis (mistral = None).
    pid = _project()
    summary = _run_summary(client, pid)
    assert summary["llm_used"] is False


def test_active_rules_counted_independently_of_llm_availability(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`active_rules` reflete les regles validees+activees meme si le LLM est
    indisponible -> les deux signaux sont independants, pas conflates."""
    monkeypatch.setattr(custom_rules, "load_rules", lambda: {
        "regles_personnalisees": [
            {"id": "a", "label": "A", "consigne": "regle active", "severity": "high"},
            {"id": "b", "label": "B", "consigne": "regle active 2", "severity": "low"},
            {"id": "c", "label": "C", "consigne": "en attente", "validated": False},
        ]
    })
    pid = _project()
    db = SessionLocal()
    try:
        set_llm_enabled(db, False)
    finally:
        db.close()

    summary = _run_summary(client, pid)
    assert summary["llm_used"] is False
    assert summary["active_rules"] == 2
