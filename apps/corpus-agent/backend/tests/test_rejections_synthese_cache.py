from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import anomalies as anomalies_api
from app.db.models import Anomaly
from app.db.session import Base, SessionLocal, engine
from app.main import create_app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield TestClient(create_app())
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_rejections_synthese_is_cached_until_rejections_change(client, monkeypatch) -> None:
    calls: list[int] = []

    class FakeClient:
        def chat(self, *_a, **_k) -> str:
            calls.append(1)
            return f"**Synthese** numero {len(calls)}"

    monkeypatch.setattr(anomalies_api.MistralClient, "from_db", classmethod(lambda cls, db: FakeClient()))
    monkeypatch.setattr(anomalies_api, "get_llm_enabled", lambda db: True)

    client.post("/api/v1/settings", json={"demo_enabled": True})
    pid = next(p["id"] for p in client.get("/api/v1/projects").json() if p["name"].startswith("Projet démo"))
    url = f"/api/v1/projects/{pid}/anomalies/rejections-summary"

    first = client.get(url).json()
    assert first["synthese"] == "Synthese numero 1" and first["cached"] is False
    second = client.get(url).json()
    assert second["synthese"] == "Synthese numero 1" and second["cached"] is True
    assert len(calls) == 1

    refreshed = client.get(url + "?refresh=true").json()
    assert refreshed["synthese"] == "Synthese numero 2" and len(calls) == 2

    with SessionLocal() as db:
        a = db.query(Anomaly).filter(Anomaly.status == "rejected").first()
        a.feedback = "Nouveau motif"
        db.commit()
    changed = client.get(url).json()
    assert changed["synthese"] == "Synthese numero 3" and changed["cached"] is False
