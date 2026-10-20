"""Tests de l'assistant de generation / modification de logigramme."""

from __future__ import annotations

import json


def _graph(client, sample_dsl) -> dict:
    return client.post("/api/v1/parse/json", json={"content": sample_dsl}).json()["graph"]


def test_assistant_fallback_generates_without_llm(client):
    text = "Verifier le fusible\nRemplacer le relais\nEssai fonctionnel"
    res = client.post("/api/v1/assistant/chat", json={"messages": [{"role": "user", "content": text}]})
    assert res.status_code == 200
    body = res.json()
    assert body["llm_used"] is False
    assert body["changed"] is True
    assert len(body["graph"]["nodes"]) >= 3
    assert body["message"]


def test_assistant_fallback_keeps_graph_unchanged(client, sample_dsl):
    graph = _graph(client, sample_dsl)
    res = client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "Ajoute un controle"}], "graph": graph},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["changed"] is False
    assert body["graph"] is None
    assert body["warnings"]


def test_assistant_rejects_last_assistant_message(client):
    res = client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "assistant", "content": "Bonjour"}]},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "ASSISTANT_TURN"


def test_assistant_llm_modifies_graph(client, sample_dsl, monkeypatch):
    from app.flow import assistant as assistant_mod

    graph = _graph(client, sample_dsl)
    updated = {**graph, "title": "Batterie - procedure revisee"}
    captured: dict = {}

    class FakeClient:
        async def chat_stream(self, messages, temperature=0.1):
            captured["messages"] = messages
            yield 'Voici : {"reply": "Titre modifie.", '
            yield '"graph": ' + json.dumps(updated) + "}"

    monkeypatch.setattr(assistant_mod.MistralClient, "from_db", classmethod(lambda cls, db: FakeClient()))
    res = client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "Renomme le titre"}], "graph": graph},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["llm_used"] is True
    assert body["changed"] is True
    assert body["message"] == "Titre modifie."
    assert body["graph"]["title"] == "Batterie - procedure revisee"
    assert "Logigramme courant" in captured["messages"][0]["content"]


def test_assistant_llm_question_without_change(client, sample_dsl, monkeypatch):
    from app.flow import assistant as assistant_mod

    class FakeClient:
        async def chat_stream(self, messages, temperature=0.1):
            yield '{"reply": "Il y a 6 etapes.", "graph": null}'

    monkeypatch.setattr(assistant_mod.MistralClient, "from_db", classmethod(lambda cls, db: FakeClient()))
    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "messages": [{"role": "user", "content": "Combien d'etapes ?"}],
            "graph": _graph(client, sample_dsl),
        },
    )
    body = res.json()
    assert body["changed"] is False
    assert body["message"] == "Il y a 6 etapes."
