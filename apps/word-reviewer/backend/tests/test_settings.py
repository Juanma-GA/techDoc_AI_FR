"""Tests /settings : round-trip du seuil de confiance LLM (anti faux positifs)."""

from __future__ import annotations


def test_confidence_threshold_default_and_roundtrip(client):
    # Defaut expose = 0.7.
    got = client.get("/api/v1/settings").json()
    assert got["llm_confidence_threshold"] == 0.7

    # Ecriture + relecture (borne a [0, 1]).
    client.post("/api/v1/settings", json={"llm_confidence_threshold": 0.85})
    assert client.get("/api/v1/settings").json()["llm_confidence_threshold"] == 0.85

    # Valeur hors bornes -> clampee.
    client.post("/api/v1/settings", json={"llm_confidence_threshold": 5})
    assert client.get("/api/v1/settings").json()["llm_confidence_threshold"] == 1.0
