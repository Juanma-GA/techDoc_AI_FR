"""Wizard end-to-end : start -> split -> type -> structure -> generate."""

from __future__ import annotations

import json

from app.core import xml_safe
from app.core.ir import IRNode, to_dict
from app.db.session import SessionLocal


def _upload(client, data: bytes) -> str:
    r = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", data)},
        data={"s1000d_issue": "5.0", "context_hint": "mixed"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_wizard_full_flow(client, pdf_bytes) -> None:
    doc_id = _upload(client, pdf_bytes)

    # start -> etape split
    st = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert st["step"] == "split"

    # re-decouper par chapitre -> 2 DMs (Description + Removal Procedure)
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"split_level": "chapter"},
    ).json()
    assert len(st["dms"]) == 2

    # avancer vers le typage
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance",
        json={"split_level": "chapter"},
    ).json()
    assert st["step"] == "type"
    types = {d["title"]: d["dm_type"] for d in st["dms"]}
    # Heuristique : "Description" -> descriptive, "Removal Procedure" -> procedural
    assert any("escription" in t for t in types)

    # avancer vers structure (sans changer les types)
    st = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"types": {}}).json()
    assert st["step"] == "structure"
    assert all("tree" in d for d in st["dms"])

    # avancer vers generation
    st = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"overrides": []}).json()
    assert st["step"] == "generate"

    # chaque DM a un XML bien forme ; le DM procedural -> <procedure>
    proc_found = False
    for d in st["dms"]:
        xml = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{d['dm_id']}/xml").text
        xml_safe.fromstring(xml, allow_internal_dtd=True)
        if d["dm_type"] == "procedural":
            assert "<procedure>" in xml
            proc_found = True
    assert proc_found, types

    # ZIP de tous les DMs
    z = client.get(f"/api/v1/documents/{doc_id}/wizard/zip")
    assert z.status_code == 200
    assert z.headers["content-type"] == "application/zip"


def test_downloaded_dm_xml_keeps_global_figure_and_table_ids(client) -> None:
    from app.db.models import Document

    with SessionLocal() as db:
        doc = Document(
            filename="manual.pdf",
            source_format="pdf",
            storage_path="unused.pdf",
            dms_json=json.dumps([
                {
                    "dm_id": "dm1",
                    "title": "First",
                    "dm_type": "descriptive",
                    "tree": to_dict(IRNode(
                        id="r1",
                        kind="section",
                        children=[IRNode(id="f1", kind="figure", text="Figure 1 First")],
                    )),
                },
                {
                    "dm_id": "dm2",
                    "title": "Second",
                    "dm_type": "descriptive",
                    "tree": to_dict(IRNode(
                        id="r2",
                        kind="section",
                        children=[
                            IRNode(id="f2", kind="figure", text="Figure 2 Second"),
                            IRNode(id="t2", kind="table", table_rows=[["A"]]),
                        ],
                    )),
                },
            ]),
        )
        db.add(doc)
        db.commit()
        doc_id = doc.id

    first = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/dm1/xml")
    second = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/dm2/xml")

    assert 'id="fig-0001"' in first.text
    assert 'id="fig-0002"' in second.text
    assert 'id="tbl-0001"' in second.text


def _split_state(client, doc_id):
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    return client.post(
        f"/api/v1/documents/{doc_id}/wizard/update", json={"split_level": "chapter"}
    ).json()


def test_split_rename_and_exclude(client, pdf_bytes) -> None:
    doc_id = _upload(client, pdf_bytes)
    st = _split_state(client, doc_id)
    assert len(st["dms"]) == 2
    first = st["dms"][0]["dm_id"]

    # renommer
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "rename", "id": first, "title": "Mon DM"},
    ).json()
    assert any(d["title"] == "Mon DM" for d in st["dms"])

    # exclure -> 1 DM restant
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "exclude", "id": first},
    ).json()
    assert len(st["dms"]) == 1


def test_rename_reassociates_available_dmrl_dmc(client, pdf_bytes, tmp_path) -> None:
    doc_id = _upload(client, pdf_bytes)
    dmrl = tmp_path / "dmrl.json"
    dmrl.write_text(json.dumps([
        {"DMC": "DMC-TEST-A-00-00-00-00A-040A-D", "Titre": "Description"},
        {"DMC": "DMC-TEST-A-00-00-00-00A-520A-D", "Titre": "Removal Procedure"},
    ]), encoding="utf-8")
    with dmrl.open("rb") as stream:
        response = client.post(
            f"/api/v1/documents/{doc_id}/resources/dmrl",
            files={"file": ("dmrl.json", stream, "application/json")},
        )
    assert response.status_code == 200, response.text
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    first = state["dms"][0]["dm_id"]
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "rename", "id": first, "title": "Removal Procedure"},
    ).json()
    assert [dm["dmc"] for dm in state["dms"]].count("DMC-TEST-A-00-00-00-00A-520A-D") == 1


def test_split_does_not_duplicate_dmrl_dmc(client, pdf_bytes, tmp_path) -> None:
    doc_id = _upload(client, pdf_bytes)
    dmrl = tmp_path / "dmrl.json"
    dmrl.write_text(json.dumps([
        {"DMC": "DMC-TEST-A-00-00-00-00A-040A-D", "Titre": "Description"},
        {"DMC": "DMC-TEST-A-00-00-00-00A-520A-D", "Titre": "Removal Procedure"},
    ]), encoding="utf-8")
    with dmrl.open("rb") as stream:
        response = client.post(
            f"/api/v1/documents/{doc_id}/resources/dmrl",
            files={"file": ("dmrl.json", stream, "application/json")},
        )
    assert response.status_code == 200, response.text
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    target = state["dms"][0]["dm_id"]
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "split", "id": target},
    ).json()
    dmcs = [dm["dmc"] for dm in state["dms"] if dm["dmc"]]
    assert len(dmcs) == len(set(dmcs))


def test_split_preserved_on_advance(client, pdf_bytes) -> None:
    """Le decoupage edite manuellement doit etre respecte a l'etape suivante :
    exclure/renommer un DM puis avancer SANS split_level ne doit pas re-decouper."""
    doc_id = _upload(client, pdf_bytes)
    st = _split_state(client, doc_id)
    assert len(st["dms"]) == 2
    first = st["dms"][0]["dm_id"]

    # Editions manuelles : renommer le 1er, exclure -> il reste 1 DM renomme.
    client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "rename", "id": first, "title": "DM conserve"},
    )
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "exclude", "id": first},
    ).json()
    assert len(st["dms"]) == 1

    # Avancer SANS split_level : l'etape type doit refleter le decoupage edite.
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance", json={}
    ).json()
    assert st["step"] == "type"
    assert len(st["dms"]) == 1, "le decoupage valide n'a pas ete respecte"


def test_advance_resplits_only_on_level_change(client, pdf_bytes) -> None:
    """Avancer AVEC un niveau different re-decoupe (comportement explicite)."""
    doc_id = _upload(client, pdf_bytes)
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")  # niveau defaut = section
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance", json={"split_level": "chapter"}
    ).json()
    assert st["step"] == "type"
    assert len(st["dms"]) == 2  # re-decoupe par chapitre


def test_split_preview_present(client, pdf_bytes) -> None:
    """L'etape split expose un apercu debut/fin avec n° de page / kind."""
    doc_id = _upload(client, pdf_bytes)
    st = _split_state(client, doc_id)
    assert st["dms"], st
    assert all("preview" in d for d in st["dms"])
    # Au moins un DM a du contenu previsualisable, snippets bien formes.
    withtext = [d for d in st["dms"] if d["preview"]["total"] >= 1]
    assert withtext, st
    for s in withtext[0]["preview"]["head"]:
        assert "page" in s and "kind" in s and "text" in s


def test_can_undo_false_right_after_start(client, pdf_bytes) -> None:
    """Un assistant fraichement demarre a une pile d'undo vide."""
    doc_id = _upload(client, pdf_bytes)
    st = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert st["step"] == "split"
    assert st["can_undo"] is False


def test_split_undo_restores(client, pdf_bytes) -> None:
    """Undo restaure un DM exclu."""
    doc_id = _upload(client, pdf_bytes)
    st = _split_state(client, doc_id)
    n0 = len(st["dms"])
    assert n0 == 2
    first = st["dms"][0]["dm_id"]

    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "exclude", "id": first},
    ).json()
    assert len(st["dms"]) == n0 - 1
    assert st["can_undo"] is True

    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update", json={"op": "undo"}
    ).json()
    assert len(st["dms"]) == n0, "undo n'a pas restaure le DM exclu"


def test_hide_zones_removes_headers_and_undo(client, pdf_bytes_headers) -> None:
    """« Masquer entetes/pieds » retire le bruit, undo le restaure."""
    doc_id = _upload(client, pdf_bytes_headers)
    st = _split_state(client, doc_id)
    before = sum(d["node_count"] for d in st["dms"])

    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "hide_zones", "zones": ["header", "footer"]},
    ).json()
    after = sum(d["node_count"] for d in st["dms"])
    assert after < before, "aucun noeud entete/pied retire"

    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update", json={"op": "undo"}
    ).json()
    assert sum(d["node_count"] for d in st["dms"]) == before


def test_split_merge(client, pdf_bytes) -> None:
    doc_id = _upload(client, pdf_bytes)
    st = _split_state(client, doc_id)
    ids = [d["dm_id"] for d in st["dms"]]
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "merge", "ids": ids},
    ).json()
    assert len(st["dms"]) == 1


def test_split_one_into_subdms() -> None:
    from app.core import ir as ir_mod
    from app.core import wizard_split
    from app.core.ir import IRNode

    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="s1", kind="section", text="1.1 Clean", level=2,
               children=[IRNode(id="p1", kind="paragraph", text="Clean it.")]),
        IRNode(id="s2", kind="section", text="1.2 Oil", level=2,
               children=[IRNode(id="p2", kind="paragraph", text="Oil it.")]),
    ])
    dm = {"dm_id": "dm1", "title": "1 Maintenance", "dm_type": "descriptive",
          "tree": ir_mod.to_dict(root), "xml": None, "violations": None}
    subs = wizard_split.split_one(dm)
    assert len(subs) == 2
    assert {s["title"] for s in subs} == {"1.1 Clean", "1.2 Oil"}


def test_wizard_type_override(client, pdf_bytes) -> None:
    doc_id = _upload(client, pdf_bytes)
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance", json={"split_level": "chapter"}
    ).json()
    # Force le 1er DM en procedural
    dm0 = st["dms"][0]["dm_id"]
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance",
        json={"types": {dm0: "procedural"}},
    ).json()
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"overrides": []})
    xml = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{dm0}/xml").text
    assert "<procedure>" in xml
