"""Tests vue document (/view, alignement surlignage, tableaux) + dashboard."""

from __future__ import annotations

import io

from tests.conftest import DOCX_MIME


def _upload_analyze(client, data):
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", data, DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    return doc_id


def test_view_blocks_and_highlight_offsets(client, make_docx):
    data = make_docx(["Chapter 250 has several parts."], headings=["GENERAL"])
    doc_id = _upload_analyze(client, data)

    view = client.get(f"/api/v1/documents/{doc_id}/view").json()
    blocks = {b["target_id"]: b for b in view["blocks"]}
    assert blocks and any(b["kind"] == "heading" for b in view["blocks"])

    sug = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    located = [s for s in sug if s["char_end"] > s["char_start"]]
    assert located, "au moins une suggestion localisee attendue"
    for s in located:
        blk = blocks.get(s["target_id"])
        assert blk is not None
        # l'offset tombe exactement sur le texte fautif -> surlignage alignE
        assert blk["text"][s["char_start"]:s["char_end"]] == s["original_text"]


def test_view_table_coords(client):
    from docx import Document

    d = Document()
    t = d.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text = "H1"; t.rows[0].cells[1].text = "H2"
    t.rows[1].cells[0].text = "a"; t.rows[1].cells[1].text = "b"
    buf = io.BytesIO(); d.save(buf)
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", buf.getvalue(), DOCX_MIME)}
    ).json()["documents"][0]["id"]

    view = client.get(f"/api/v1/documents/{doc_id}/view").json()
    cells = [b for b in view["blocks"] if b["kind"] == "cell"]
    assert len(cells) >= 4
    assert all(c["table_id"] is not None for c in cells)
    assert {(c["row"], c["col"]) for c in cells} >= {(0, 0), (0, 1), (1, 0), (1, 1)}


def test_ata_chapter_ref_is_corrective(client, make_docx):
    client.post("/api/v1/admin/reset/all")
    doc_id = _upload_analyze(client, make_docx(["See 34.10.42 and also 24-21-00."]))
    refs = [s for s in client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
            if s["rule_code"] == "ATA_CHAPTER_REF"]
    # la reference bien formee (24-21-00) n'est pas signalee ; la mal formee l'est
    assert len(refs) == 1
    assert refs[0]["original_text"] == "34.10.42"
    assert refs[0]["proposed_text"] == "34-10-42"  # propose une vraie modification


def test_dashboard_aggregates(client, make_docx):
    client.post("/api/v1/admin/reset/all")
    doc_id = _upload_analyze(client, make_docx(["Chapter 250 several parts."]))
    dash = client.get("/api/v1/admin/dashboard").json()
    assert dash["documents"] >= 1
    assert sum(dash["by_status"].values()) >= 1
    assert sum(dash["by_severity"].values()) >= 1
    # le document figure dans le top (anomalies ouvertes)
    assert any(td["id"] == doc_id and td["open_count"] >= 1 for td in dash["top_documents"])


def test_dashboard_by_topic_present(client, make_docx):
    client.post("/api/v1/admin/reset/all")
    _upload_analyze(client, make_docx(["Chapter 250 several parts."]))
    dash = client.get("/api/v1/admin/dashboard").json()
    assert "by_topic" in dash
    # somme par topic == somme totale des suggestions (meme population que by_severity).
    # Les regles standard (rule_id NULL) tombent dans le bucket de repli.
    assert sum(dash["by_topic"].values()) == sum(dash["by_severity"].values()) >= 1
    assert "Controles standard" in dash["by_topic"]
