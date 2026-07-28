"""Routes /api/v1/documents — upload TXT, list, delete, dedup sha256.

Pas de Mistral configuré : on vérifie que l'upload réussit quand même
(parsing OK, index marqué en erreur)."""

from __future__ import annotations

import io


def _upload(client, filename: str, payload: bytes):
    return client.post(
        "/api/v1/documents",
        files={"files": (filename, io.BytesIO(payload), "text/plain")},
    )


def test_upload_then_list_and_delete(client) -> None:
    r = _upload(client, "note.txt", b"contenu de test pour doc-writer")
    assert r.status_code == 200, r.text
    items = r.json()["uploaded"]
    assert len(items) == 1
    item = items[0]
    assert item["ok"] is True
    assert item["filename"] == "note.txt"
    doc_id = item["document_id"]

    # list
    r2 = client.get("/api/v1/documents")
    assert r2.status_code == 200
    docs = r2.json()
    assert len(docs) == 1
    assert docs[0]["filename"] == "note.txt"
    assert docs[0]["sha256"]
    # Pas de Mistral configuré → index_error renseigné
    assert docs[0]["index_error"] == "MISTRAL_NOT_CONFIGURED"

    # delete
    r3 = client.delete(f"/api/v1/documents/{doc_id}")
    assert r3.status_code == 204
    assert client.get("/api/v1/documents").json() == []


def test_reparse_source_reextracts(client) -> None:
    r = _upload(client, "note.txt", b"contenu initial du document")
    doc_id = r.json()["uploaded"][0]["document_id"]

    r2 = client.post(f"/api/v1/documents/{doc_id}/reparse")
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["id"] == doc_id
    # Pas de Mistral configure -> re-indexation impossible -> index_error pose.
    assert body["index_error"] == "MISTRAL_NOT_CONFIGURED"


def test_content_returns_extracted_text(client) -> None:
    r = _upload(client, "note.txt", b"Anglais B2. Espagnol courant.")
    doc_id = r.json()["uploaded"][0]["document_id"]

    r2 = client.get(f"/api/v1/documents/{doc_id}/content")
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["id"] == doc_id
    assert "Anglais B2" in body["text"]
    assert body["char_count"] == len(body["text"])


def test_content_unknown_returns_404(client) -> None:
    import uuid

    r = client.get(f"/api/v1/documents/{uuid.uuid4()}/content")
    assert r.status_code == 404


def test_reparse_unknown_returns_404(client) -> None:
    import uuid

    r = client.post(f"/api/v1/documents/{uuid.uuid4()}/reparse")
    assert r.status_code == 404


def test_reparse_template_refused(client) -> None:
    r = client.post(
        "/api/v1/documents",
        files={"files": ("modele.txt", io.BytesIO(b"libelle xxx"), "text/plain")},
        data={"kind": "template"},
    )
    doc_id = r.json()["uploaded"][0]["document_id"]

    r2 = client.post(f"/api/v1/documents/{doc_id}/reparse")
    assert r2.status_code == 400
    assert r2.json()["code"] == "REPARSE_UNSUPPORTED_TEMPLATE"


def test_upload_dedup_on_sha256(client) -> None:
    payload = b"identique"
    r1 = _upload(client, "a.txt", payload)
    assert r1.status_code == 200
    r2 = _upload(client, "b.txt", payload)
    assert r2.status_code == 200
    assert r2.json()["uploaded"][0]["skipped"] == "duplicate"

    docs = client.get("/api/v1/documents").json()
    assert len(docs) == 1


def test_upload_rejects_unsupported_extension(client) -> None:
    r = _upload(client, "evil.exe", b"binary garbage")
    assert r.status_code == 200
    item = r.json()["uploaded"][0]
    assert item["ok"] is False
    assert "extension" in (item["error"] or "").lower() or "autorisée" in (item["error"] or "").lower()


def test_delete_unknown_document_returns_404(client) -> None:
    r = client.delete("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "DOCUMENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Zones : toggle actif/inactif (PATCH) persiste dans le cache du template.
# ---------------------------------------------------------------------------

_PPTX_MIME = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


def _pptx_with_two_xxx_zones() -> bytes:
    """Template deterministe (zones XXX, pas besoin de Mistral)."""
    from pptx import Presentation  # type: ignore[import-untyped]
    from pptx.util import Inches  # type: ignore[import-untyped]

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    if slide.shapes.title is not None:
        slide.shapes.title.text = "Titre"
    tb = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(3))
    tf = tb.text_frame
    tf.text = "Contexte : XXX"
    tf.add_paragraph().text = "Resultat : XXX"
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _upload_template(client, payload: bytes):
    return client.post(
        "/api/v1/documents",
        files={"files": ("template.pptx", io.BytesIO(payload), _PPTX_MIME)},
        data={"kind": "template"},
    )


def test_zone_toggle_persists(client) -> None:
    up = _upload_template(client, _pptx_with_two_xxx_zones())
    assert up.status_code == 200, up.text
    doc_id = up.json()["uploaded"][0]["document_id"]

    z = client.get(f"/api/v1/documents/{doc_id}/zones")
    assert z.status_code == 200, z.text
    zones = z.json()["zones"]
    # 2 marqueurs XXX + tous les autres cadres (titre...) listes, tous actifs.
    assert len(zones) >= 2
    assert all(zz["active"] for zz in zones)  # actives par defaut

    target = zones[0]["id"]
    patch = client.patch(
        f"/api/v1/documents/{doc_id}/zones/{target}", json={"active": False}
    )
    assert patch.status_code == 200, patch.text
    patched = {zz["id"]: zz["active"] for zz in patch.json()["zones"]}
    assert patched[target] is False

    # Persistance : un nouveau GET reflete l'etat (pas un reset).
    z2 = client.get(f"/api/v1/documents/{doc_id}/zones")
    got = {zz["id"]: zz["active"] for zz in z2.json()["zones"]}
    assert got[target] is False
    assert got[zones[1]["id"]] is True


def test_zone_instruction_persists_and_keeps_validation(client) -> None:
    up = _upload_template(client, _pptx_with_two_xxx_zones())
    doc_id = up.json()["uploaded"][0]["document_id"]

    z = client.get(f"/api/v1/documents/{doc_id}/zones").json()
    target = z["zones"][0]["id"]
    # Template a marqueurs XXX seuls (0 rejet) -> auto-valide.
    assert z["validated"] is True
    assert z["zones"][0]["instruction"] == ""

    patch = client.patch(
        f"/api/v1/documents/{doc_id}/zones/{target}",
        json={"instruction": "3 puces maximum, ton commercial"},
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    # Consigne = non structurel -> la validation est preservee.
    assert body["validated"] is True
    by_id = {zz["id"]: zz for zz in body["zones"]}
    assert by_id[target]["instruction"] == "3 puces maximum, ton commercial"

    # Persistance sur un nouveau GET.
    z2 = client.get(f"/api/v1/documents/{doc_id}/zones").json()
    got = {zz["id"]: zz for zz in z2["zones"]}
    assert got[target]["instruction"] == "3 puces maximum, ton commercial"


def test_zone_soft_delete_then_restore(client) -> None:
    up = _upload_template(client, _pptx_with_two_xxx_zones())
    doc_id = up.json()["uploaded"][0]["document_id"]

    zones = client.get(f"/api/v1/documents/{doc_id}/zones").json()["zones"]
    target = zones[0]["id"]

    # Suppression -> la zone passe dans `removed`, plus dans `zones`.
    d = client.delete(f"/api/v1/documents/{doc_id}/zones/{target}")
    assert d.status_code == 200, d.text
    body = d.json()
    assert target not in {z["id"] for z in body["zones"]}
    assert target in {z["id"] for z in body["removed"]}

    # Persiste sur un nouveau GET.
    g = client.get(f"/api/v1/documents/{doc_id}/zones").json()
    assert target in {z["id"] for z in g["removed"]}

    # Restauration -> revient dans `zones`, sort de `removed`.
    r = client.post(f"/api/v1/documents/{doc_id}/zones/{target}/restore")
    assert r.status_code == 200, r.text
    rb = r.json()
    assert target in {z["id"] for z in rb["zones"]}
    assert target not in {z["id"] for z in rb["removed"]}


# ---------------------------------------------------------------------------
# Reanalyse (POST /zones/reanalyse) : redetection qui preserve les edits.
# ---------------------------------------------------------------------------


def _storage_path(doc_id: str):  # type: ignore[no-untyped-def]
    """Chemin disque du fichier stocke pour ce document (acces direct DB, cf.
    conventions des autres tests de cette suite, ex. test_writer_engine_scope)."""
    import uuid as uuid_mod

    from app.db.models import Document
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        doc = db.get(Document, uuid_mod.UUID(doc_id))
        return doc.storage_path
    finally:
        db.close()


def test_reanalyse_preserves_edited_label_and_instruction(client) -> None:
    # Fixture a 2 marqueurs XXX dans la MEME shape (donc meme `target` au
    # niveau shape) : verifie que la fusion distingue bien les deux zones
    # entre elles (cf. `_target_occurrence_map`), pas seulement par `target`.
    up = _upload_template(client, _pptx_with_two_xxx_zones())
    doc_id = up.json()["uploaded"][0]["document_id"]

    zones = client.get(f"/api/v1/documents/{doc_id}/zones").json()["zones"]
    edited, untouched = zones[0], zones[1]
    assert edited["target"]  # sinon le test ne prouve rien (pas de cle de fusion)
    assert edited["target"] == untouched["target"]  # meme shape, cas le plus dur

    patch = client.patch(
        f"/api/v1/documents/{doc_id}/zones/{edited['id']}",
        json={"label": "Libelle edite a la main", "instruction": "Ton commercial"},
    )
    assert patch.status_code == 200, patch.text

    # Reanalyse : le FICHIER n'a pas change, mais le endpoint redetecte quand
    # meme tout depuis zero puis fusionne -> l'edit doit survivre, SANS
    # deteindre sur l'autre zone qui partage le meme target.
    r = client.post(f"/api/v1/documents/{doc_id}/zones/reanalyse")
    assert r.status_code == 200, r.text
    by_id = {z["id"]: z for z in r.json()["zones"]}
    assert by_id[edited["id"]]["label"] == "Libelle edite a la main"
    assert by_id[edited["id"]]["instruction"] == "Ton commercial"
    assert by_id[untouched["id"]]["label"] == untouched["label"]
    assert by_id[untouched["id"]]["instruction"] == ""

    # Persiste sur un GET ulterieur (pas juste dans la reponse du POST).
    g = client.get(f"/api/v1/documents/{doc_id}/zones").json()
    got = {z["id"]: z for z in g["zones"]}
    assert got[edited["id"]]["label"] == "Libelle edite a la main"
    assert got[untouched["id"]]["label"] == untouched["label"]


def test_reanalyse_keeps_removed_zone_trashed(client) -> None:
    up = _upload_template(client, _pptx_with_two_xxx_zones())
    doc_id = up.json()["uploaded"][0]["document_id"]

    zones = client.get(f"/api/v1/documents/{doc_id}/zones").json()["zones"]
    removed_zone, sibling = zones[0], zones[1]
    assert removed_zone["target"] == sibling["target"]  # meme shape

    d = client.delete(f"/api/v1/documents/{doc_id}/zones/{removed_zone['id']}")
    assert d.status_code == 200, d.text

    r = client.post(f"/api/v1/documents/{doc_id}/zones/reanalyse")
    assert r.status_code == 200, r.text
    body = r.json()
    zone_ids = {z["id"] for z in body["zones"]}
    removed_ids = {z["id"] for z in body["removed"]}
    # La redetection revoit bien la shape dans le fichier (son voisin de meme
    # target est toujours actif), mais la zone supprimee reste a la corbeille
    # -> ne doit pas resurgir active.
    assert removed_zone["id"] not in zone_ids
    assert removed_zone["id"] in removed_ids
    assert sibling["id"] in zone_ids


def test_reanalyse_detects_new_shape_added_to_template(client) -> None:
    from pptx import Presentation  # type: ignore[import-untyped]
    from pptx.util import Inches  # type: ignore[import-untyped]

    up = _upload_template(client, _pptx_with_two_xxx_zones())
    doc_id = up.json()["uploaded"][0]["document_id"]

    zones_before = client.get(f"/api/v1/documents/{doc_id}/zones").json()["zones"]
    targets_before = {z["target"] for z in zones_before}

    # Edite le fichier stocke : ajoute un 3e cadre XXX sur la meme slide.
    # Les shapes existantes gardent leur shape_id (python-pptx les assigne a
    # la creation, jamais renumerotees par un ajout), donc leurs `target`
    # restent stables.
    path = _storage_path(doc_id)
    prs = Presentation(path)
    tb = prs.slides[0].shapes.add_textbox(Inches(1), Inches(5), Inches(6), Inches(1))
    tb.text_frame.text = "Nouveau : XXX"
    prs.save(path)

    r = client.post(f"/api/v1/documents/{doc_id}/zones/reanalyse")
    assert r.status_code == 200, r.text
    body = r.json()
    targets_after = {z["target"] for z in body["zones"]}

    # Les zones deja connues sont toujours la (memes targets).
    assert targets_before <= targets_after
    # La nouvelle shape est detectee en plus, pas a la place des anciennes.
    assert len(targets_after) > len(targets_before)


def test_get_zones_ignores_legacy_refresh_query_param(client) -> None:
    """`GET .../zones` est une lecture pure : un `?refresh=true` residuel (ancien
    client, favori navigateur) ne doit jamais ecraser une configuration
    existante — seul `POST .../zones/reanalyse` redetecte."""
    up = _upload_template(client, _pptx_with_two_xxx_zones())
    doc_id = up.json()["uploaded"][0]["document_id"]

    zones = client.get(f"/api/v1/documents/{doc_id}/zones").json()["zones"]
    zone_id = zones[0]["id"]
    client.patch(
        f"/api/v1/documents/{doc_id}/zones/{zone_id}",
        json={"label": "Ne doit jamais disparaitre"},
    )

    g = client.get(f"/api/v1/documents/{doc_id}/zones?refresh=true")
    assert g.status_code == 200, g.text
    by_id = {z["id"]: z for z in g.json()["zones"]}
    assert by_id[zone_id]["label"] == "Ne doit jamais disparaitre"


_DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _docx_with_marker_zones() -> bytes:
    """Template Word deterministe : un {{cle}} et un marqueur XXX."""
    from docx import Document  # type: ignore[import-untyped]

    doc = Document()
    doc.add_paragraph("Titre : {{titre}}")
    doc.add_paragraph("Contexte : XXX")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_docx_template_exposes_zones(client) -> None:
    """Un template .docx expose ses zones via la meme route que le .pptx
    (generalisation du dispatcher de format)."""
    up = client.post(
        "/api/v1/documents",
        files={"files": ("template.docx", io.BytesIO(_docx_with_marker_zones()), _DOCX_MIME)},
        data={"kind": "template"},
    )
    assert up.status_code == 200, up.text
    doc_id = up.json()["uploaded"][0]["document_id"]

    z = client.get(f"/api/v1/documents/{doc_id}/zones")
    assert z.status_code == 200, z.text
    zones = z.json()["zones"]
    kinds = {zz["kind"] for zz in zones}
    assert "placeholder" in kinds
    assert "xxx" in kinds


def test_flow_returns_blocks_for_docx(client) -> None:
    """L'apercu 'flux' Word liste les blocs (paragraphes a marqueur inclus)."""
    up = client.post(
        "/api/v1/documents",
        files={"files": ("template.docx", io.BytesIO(_docx_with_marker_zones()), _DOCX_MIME)},
        data={"kind": "template"},
    )
    doc_id = up.json()["uploaded"][0]["document_id"]

    r = client.get(f"/api/v1/documents/{doc_id}/flow")
    assert r.status_code == 200, r.text
    blocks = r.json()["blocks"]
    assert blocks
    assert any(b["has_marker"] for b in blocks)
    assert all(b["id"] for b in blocks)


def test_flow_refused_for_pptx(client) -> None:
    """L'apercu 'flux' ne concerne que Word/PDF : 400 pour un .pptx."""
    up = _upload_template(client, _pptx_with_two_xxx_zones())
    doc_id = up.json()["uploaded"][0]["document_id"]
    r = client.get(f"/api/v1/documents/{doc_id}/flow")
    assert r.status_code == 400
    assert r.json()["code"] == "FLOW_UNSUPPORTED"


def test_restore_unknown_zone_returns_404(client) -> None:
    up = _upload_template(client, _pptx_with_two_xxx_zones())
    doc_id = up.json()["uploaded"][0]["document_id"]
    client.get(f"/api/v1/documents/{doc_id}/zones")  # peuple le cache
    r = client.post(f"/api/v1/documents/{doc_id}/zones/z_999/restore")
    assert r.status_code == 404
    assert r.json()["code"] == "ZONE_NOT_FOUND"


def test_zone_toggle_unknown_zone_returns_404(client) -> None:
    up = _upload_template(client, _pptx_with_two_xxx_zones())
    doc_id = up.json()["uploaded"][0]["document_id"]
    # GET prealable : peuple le cache des zones (sinon PATCH -> ZONES_NOT_ANALYSED).
    assert client.get(f"/api/v1/documents/{doc_id}/zones").status_code == 200
    r = client.patch(
        f"/api/v1/documents/{doc_id}/zones/z_999", json={"active": False}
    )
    assert r.status_code == 404
    assert r.json()["code"] == "ZONE_NOT_FOUND"
