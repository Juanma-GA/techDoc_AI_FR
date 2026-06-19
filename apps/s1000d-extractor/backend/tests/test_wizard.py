"""Wizard end-to-end : start -> split -> type -> structure -> generate."""

from __future__ import annotations

from lxml import etree


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
        etree.fromstring(xml.encode("utf-8"))
        if d["dm_type"] == "procedural":
            assert "<procedure>" in xml
            proc_found = True
    assert proc_found, types

    # ZIP de tous les DMs
    z = client.get(f"/api/v1/documents/{doc_id}/wizard/zip")
    assert z.status_code == 200
    assert z.headers["content-type"] == "application/zip"


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
    from app.core import wizard
    from app.core.ir import IRNode

    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="s1", kind="section", text="1.1 Clean", level=2,
               children=[IRNode(id="p1", kind="paragraph", text="Clean it.")]),
        IRNode(id="s2", kind="section", text="1.2 Oil", level=2,
               children=[IRNode(id="p2", kind="paragraph", text="Oil it.")]),
    ])
    dm = {"dm_id": "dm1", "title": "1 Maintenance", "dm_type": "descriptive",
          "tree": ir_mod.to_dict(root), "xml": None, "violations": None}
    subs = wizard._split_one(dm)
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
