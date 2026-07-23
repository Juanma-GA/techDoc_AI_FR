"""Tests de la vue PDF fidele : rendu PNG par page + bbox des anomalies.

La chaine docx->PDF depend de LibreOffice. Si absent (CI), l'endpoint renvoie
`available=false` et on verifie juste la degradation gracieuse. Sur un poste avec
LibreOffice, on verifie page_count + surlignage.
"""

from __future__ import annotations

from tests.conftest import DOCX_MIME


def _add_rule(client, **kw):
    payload = {"name": kw.get("name", "rule"), "kind": kw["kind"], "validated": True}
    payload.update(kw)
    return client.post("/api/v1/rules", json=payload).json()


def test_pdf_view_and_page_png(client, make_docx):
    client.post("/api/v1/admin/reset/rules")
    _add_rule(client, name="Rename SEXTANT", kind="regex_replace", pattern="SEXTANT", replacement="THALES")
    data = make_docx(["Le composant SEXTANT est critique."])
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", data, DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})

    view = client.get(f"/api/v1/documents/{doc_id}/pdf-view")
    assert view.status_code == 200
    body = view.json()

    if not body["available"]:
        # Pas de LibreOffice : degradation gracieuse, le front retombe sur le HTML.
        png = client.get(f"/api/v1/documents/{doc_id}/pages/1.png")
        assert png.status_code == 503
        return

    assert body["page_count"] >= 1
    # L'anomalie sur "SEXTANT" doit etre localisee (au moins une box).
    hl = [h for h in body["highlights"] if h["boxes"]]
    assert hl, "aucune anomalie localisee sur le PDF"
    box = hl[0]["boxes"][0]
    assert 0 <= box["left"] <= 100 and 0 < box["width"] <= 100

    png = client.get(f"/api/v1/documents/{doc_id}/pages/1.png")
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"  # signature PNG


def test_compute_highlights_dedups_duplicate_text(tmp_path):
    """Un texte present 2x -> 2 anomalies, chacune UNE boite distincte (pas de
    boites superposees qui detournent le clic vers la mauvaise anomalie)."""
    import fitz

    from app.core.pdf_render import compute_highlights

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "ANOMALIE ici")
    page.insert_text((72, 400), "ANOMALIE la")
    pdf = tmp_path / "dup.pdf"
    doc.save(str(pdf))
    doc.close()

    # Deux anomalies portant le meme texte, en ordre de lecture.
    res = compute_highlights(pdf, [("s1", "ANOMALIE"), ("s2", "ANOMALIE")])
    hls = {h["id"]: h for h in res["highlights"]}
    assert set(hls) == {"s1", "s2"}
    assert len(hls["s1"]["boxes"]) == 1 and len(hls["s2"]["boxes"]) == 1
    # Chacune sur une occurrence differente : s1 (haut) avant s2 (bas).
    assert hls["s1"]["boxes"][0]["top"] < hls["s2"]["boxes"][0]["top"]


def test_compute_highlights_more_sugs_than_occurrences(tmp_path):
    """3 anomalies pour 1 seule occurrence : la 1re est localisee, les autres
    n'ont pas de fausse boite (mieux qu'une boite superposee erronee)."""
    import fitz

    from app.core.pdf_render import compute_highlights

    doc = fitz.open()
    doc.new_page().insert_text((72, 120), "UNIQUE token")
    pdf = tmp_path / "uni.pdf"
    doc.save(str(pdf))
    doc.close()

    res = compute_highlights(pdf, [("a", "UNIQUE"), ("b", "UNIQUE"), ("c", "UNIQUE")])
    ids = {h["id"] for h in res["highlights"]}
    assert ids == {"a"}  # seule la 1re occurrence est attribuee


def test_looks_like_title_filters_non_titles():
    """Les fragments a grosse police mais non-titres ne doivent pas etre pris pour
    des titres (numero ATA, marqueur, date, note de bas de page)."""
    from app.core.layout_checks import _looks_like_title

    assert not _looks_like_title("34-20-12")      # numero ATA
    assert not _looks_like_title("TP 2")          # marqueur court
    assert not _looks_like_title("APR 22/26")     # date
    assert not _looks_like_title("* indicates pages modified")  # note (asterisque)
    assert _looks_like_title("GENERAL")           # vrai titre mono-mot
    assert _looks_like_title("RECORD OF REVISIONS")


def test_layout_checks_title_not_centered(client, make_docx):
    # Un titre (add_heading) est aligne a GAUCHE par defaut -> non centre.
    # Plusieurs lignes de corps pour que la mediane des tailles = taille du corps.
    body = [f"Ligne de corps numero {i} du document de controle." for i in range(8)]
    data = make_docx(body, headings=["TITRE A GAUCHE"])
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", data, DOCX_MIME)}
    ).json()["documents"][0]["id"]

    res = client.get(f"/api/v1/documents/{doc_id}/layout-checks")
    assert res.status_code == 200
    body = res.json()
    if not body["available"]:
        return  # pas de convertisseur PDF : degradation gracieuse
    codes = {f["rule_code"] for f in body["findings"]}
    assert "LAYOUT_TITLE_CENTER" in codes
    hit = next(f for f in body["findings"] if f["rule_code"] == "LAYOUT_TITLE_CENTER")
    assert hit["page"] == 1 and hit["boxes"]
