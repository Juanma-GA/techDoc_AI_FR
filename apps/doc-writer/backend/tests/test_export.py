"""Route /api/v1/sessions/{id}/export.

Couvre les chemins deterministes (sans Mistral) :
- export `md` renvoie le dernier message assistant tel quel ;
- export `pptx` sur une session sans template attache echoue avec
  TEMPLATE_REQUIRED, avant tout appel a Mistral.

Le pipeline de remplissage PPTX (preview/refill/render + gating de
validation des zones) depend de Mistral et n'est pas teste ici.
"""

from __future__ import annotations

import uuid


def _seed_assistant_message(session_id: str, content: str = "Contenu genere.") -> None:
    from app.db.models import Message
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        db.add(
            Message(
                session_id=uuid.UUID(session_id),
                role="assistant",
                content=content,
            )
        )
        db.commit()
    finally:
        db.close()


def _new_session(client, **overrides):
    payload = {
        "title": "exp",
        "scope_doc_ids": [],
        "lang": "fr",
    }
    payload.update(overrides)
    return client.post("/api/v1/sessions", json=payload)


def _docx_template_bytes() -> bytes:
    import io

    from docx import Document

    doc = Document()
    doc.add_paragraph("Titre : {{titre}}")
    doc.add_paragraph("Paragraphe de prose fixe.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_preview_pptx_returns_active_flag(client) -> None:
    """La reponse preview inclut `active` par zone (le front s'en sert pour
    pre-cocher les zones a ignorer). LLM off -> mapping vide, pas d'appel Mistral."""
    import io

    _DOCX_MIME = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    up = client.post(
        "/api/v1/documents",
        files={"files": ("tpl.docx", io.BytesIO(_docx_template_bytes()), _DOCX_MIME)},
        data={"kind": "template"},
    )
    assert up.status_code == 200, up.text
    doc_id = up.json()["uploaded"][0]["document_id"]
    # Peuple le cache des zones.
    assert client.get(f"/api/v1/documents/{doc_id}/zones").status_code == 200

    sess = _new_session(client, template_doc_id=doc_id)
    assert sess.status_code == 200, sess.text
    session_id = sess.json()["id"]
    _seed_assistant_message(session_id, "Contenu genere.")

    # LLM OFF -> _build_mapping_for_zones renvoie un mapping vide sans appeler
    # Mistral (llm_enabled defaut True, independant de la cle).
    assert client.post(
        "/api/v1/settings", json={"llm_enabled": False}
    ).status_code == 200

    r = client.post(f"/api/v1/sessions/{session_id}/preview-pptx")
    assert r.status_code == 200, r.text
    zones = r.json()["zones"]
    assert zones
    assert all("active" in z and isinstance(z["active"], bool) for z in zones)


def test_export_md_returns_assistant_content(client) -> None:
    sess = _new_session(client)
    assert sess.status_code == 200, sess.text
    session_id = sess.json()["id"]
    _seed_assistant_message(session_id, "Mon rapport genere.")

    r = client.get(f"/api/v1/sessions/{session_id}/export?format=md")
    assert r.status_code == 200, r.text
    assert "Mon rapport genere." in r.text
    assert r.headers["content-type"].startswith("text/markdown")


def test_export_pptx_without_template_returns_template_required(client) -> None:
    sess = _new_session(client)
    session_id = sess.json()["id"]
    _seed_assistant_message(session_id)

    r = client.get(f"/api/v1/sessions/{session_id}/export?format=pptx")
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "TEMPLATE_REQUIRED"


def test_export_without_content_returns_404(client) -> None:
    sess = _new_session(client)
    session_id = sess.json()["id"]

    r = client.get(f"/api/v1/sessions/{session_id}/export?format=md")
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "NOTHING_TO_EXPORT"


def test_export_pdf_without_template_stays_pdf(client) -> None:
    """Sans template attache, l'export pdf reste un rendu markdown -> pdf (le
    routage 'remplir -> .docx' ne s'active QUE avec un template Word/PDF)."""
    sess = _new_session(client)
    session_id = sess.json()["id"]
    _seed_assistant_message(session_id, "# Titre\n\nUn paragraphe.")

    r = client.get(f"/api/v1/sessions/{session_id}/export?format=pdf")
    assert r.status_code == 200, r.text
    assert r.content[:5] == b"%PDF-"
    assert ".pdf" in r.headers["content-disposition"]


def test_export_docx_without_template_stays_docx(client) -> None:
    """Sans template, docx = conversion markdown generique (conteneur zip PK)."""
    sess = _new_session(client)
    session_id = sess.json()["id"]
    _seed_assistant_message(session_id, "# Titre\n\nUn paragraphe.")

    r = client.get(f"/api/v1/sessions/{session_id}/export?format=docx")
    assert r.status_code == 200, r.text
    assert r.content[:2] == b"PK"
    assert ".docx" in r.headers["content-disposition"]


# ---------------------------------------------------------------------------
# Dedup deterministe du mapping (doublons) : intra-zone + inter-zones paralleles
# ---------------------------------------------------------------------------


def _zone(zid: str, label: str):
    from app.core.pptx_template import Zone

    return Zone(
        id=zid,
        kind="frame",
        slide_index=1,
        slide_title="",
        label=label,
        location="",
        target=f"s_1_{zid}",
    )


def test_dedupe_within_zone_drops_repeated_bullets() -> None:
    """Items identiques dans une meme zone liste -> 1 seule occurrence (compare
    sans accents/casse/puce), ordre conserve."""
    from app.api.export import _dedupe_within_zone

    val = "- AutoCAD\n- CATIA\n- autocad\n- CATIA"
    assert _dedupe_within_zone(val) == "- AutoCAD\n- CATIA"


def test_dedupe_within_zone_keeps_distinct_lines() -> None:
    from app.api.export import _dedupe_within_zone

    val = "- Francais (langue maternelle)\n- Anglais (C1)"
    assert _dedupe_within_zone(val) == val


def test_dedupe_across_zones_blanks_duplicate_parallel_zone() -> None:
    """Meme contenu complet dans deux zones de MEME label -> la 2e est videe."""
    from app.api.export import _dedupe_across_zones

    zones = [_zone("a", "Experience"), _zone("b", "Experience")]
    mapping = {"a": "Chef de projet chez ACME", "b": "Chef de projet chez ACME"}
    _dedupe_across_zones(mapping, zones)
    assert mapping["a"] == "Chef de projet chez ACME"
    assert mapping["b"] == ""


def test_dedupe_across_zones_keeps_different_content() -> None:
    from app.api.export import _dedupe_across_zones

    zones = [_zone("a", "Experience"), _zone("b", "Experience")]
    mapping = {"a": "Poste A", "b": "Poste B"}
    _dedupe_across_zones(mapping, zones)
    assert mapping == {"a": "Poste A", "b": "Poste B"}


def test_dedupe_across_zones_scoped_by_label() -> None:
    """Deux zones de labels DIFFERENTS avec le meme contenu ne sont pas
    deduppees (dedup limite aux zones paralleles de meme label)."""
    from app.api.export import _dedupe_across_zones

    zones = [_zone("a", "Resume"), _zone("b", "Objectif")]
    mapping = {"a": "Ingenieur mecanique", "b": "Ingenieur mecanique"}
    _dedupe_across_zones(mapping, zones)
    assert mapping["a"] == "Ingenieur mecanique"
    assert mapping["b"] == "Ingenieur mecanique"
