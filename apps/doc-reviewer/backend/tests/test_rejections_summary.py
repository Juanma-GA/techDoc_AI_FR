"""Synthèse des rejets : GET /api/v1/suggestions/rejections-summary.

Agrégat déterministe par règle + fallback gracieux de la synthèse IA (pas de
clé Mistral en test -> synthese vide, aucun appel réseau)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.db.models import Document, Suggestion
from app.db.session import SessionLocal


def _doc_with_rejections() -> None:
    db = SessionLocal()
    try:
        # L'endpoint agrege TOUS les rejets : on repart d'une table propre pour
        # des comptes deterministes (la conftest ne reset pas entre tests).
        db.query(Suggestion).delete()
        db.query(Document).delete()
        db.commit()
        doc = Document(
            original_filename="manual.pdf",
            sha256="a" * 64,
            storage_dir=f"document_{uuid.uuid4().hex}",
        )
        db.add(doc)
        db.flush()
        db.add_all([
            Suggestion(document_id=doc.id, rule_kind="standard", rule_code="STE_PASSIVE_VOICE",
                       message="m1", status="rejected", feedback="faux positif"),
            Suggestion(document_id=doc.id, rule_kind="standard", rule_code="STE_PASSIVE_VOICE",
                       message="m2", status="rejected", feedback="hors perimetre"),
            Suggestion(document_id=doc.id, rule_kind="units", rule_code="UNIT_CONVERT",
                       message="m3", status="rejected", feedback=""),
            Suggestion(document_id=doc.id, rule_kind="custom", rule_code="AI_SCAN",
                       source_kind="ai", message="m5", status="rejected", feedback="IA"),
            # une suggestion OUVERTE ne doit pas compter
            Suggestion(document_id=doc.id, rule_kind="standard", rule_code="STE_FIRST_PERSON",
                       message="m4", status="open"),
        ])
        db.commit()
    finally:
        db.close()


def test_rejections_summary_aggregates(client: TestClient) -> None:
    _doc_with_rejections()
    r = client.get("/api/v1/suggestions/rejections-summary?synthesize=false")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 4
    by_rule = {c["rule_code"]: c["count"] for c in body["by_rule"]}
    assert by_rule == {"STE_PASSIVE_VOICE": 2, "UNIT_CONVERT": 1, "AI_SCAN": 1}
    assert body["by_rule"][0]["rule_code"] == "STE_PASSIVE_VOICE"  # tri desc
    # items exploitables (parite corpus-agent) : fichier + regle + motif.
    assert len(body["items"]) == 4
    assert all(i["file"] == "manual.pdf" for i in body["items"])
    assert len({i["document_id"] for i in body["items"]}) == 1
    assert all(uuid.UUID(i["document_id"]) for i in body["items"])
    ai_item = next(item for item in body["items"] if item["rule_code"] == "AI_SCAN")
    assert ai_item["source_kind"] == "ai"
    motifs = {i["feedback"] for i in body["items"]}
    assert "faux positif" in motifs and "hors perimetre" in motifs
    assert body["synthese"] == ""
    assert body["llm_used"] is False


def test_rejections_summary_ai_graceful(client: TestClient) -> None:
    """synthesize=true mais LLM OFF -> pas d'appel réseau, agrégat seul."""
    from app.core.mistral_settings import set_llm_enabled

    _doc_with_rejections()
    db = SessionLocal()
    try:
        set_llm_enabled(db, False)
    finally:
        db.close()
    try:
        r = client.get("/api/v1/suggestions/rejections-summary?synthesize=true")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 4
        assert body["synthese"] == ""
        assert body["llm_used"] is False
    finally:
        db2 = SessionLocal()
        try:
            set_llm_enabled(db2, True)
        finally:
            db2.close()
