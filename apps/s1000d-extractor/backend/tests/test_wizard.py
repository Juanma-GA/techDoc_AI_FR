"""Wizard end-to-end : start -> split -> type -> structure -> generate."""

from __future__ import annotations

import json
from io import BytesIO
from zipfile import ZipFile

from app.core import xml_safe
from app.core.ir import IRNode, to_dict
from app.db.session import SessionLocal


def _upload(client, data: bytes) -> str:
    r = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", data)},
        data={"s1000d_issue": "4.2", "context_hint": "mixed"},
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    detection = client.post(f"/api/v1/documents/{doc_id}/pdf-cut/detect")
    assert detection.status_code == 200, detection.text
    cut = detection.json()
    if cut["validation_required"]:
        confirmation = client.post(
            f"/api/v1/documents/{doc_id}/pdf-cut/confirm",
            json={
                "start_page": cut["selected_page"] or cut["default_start_page"],
                "end_page": cut["selected_end_page"] or cut["total_pages"],
            },
        )
        assert confirmation.status_code == 200, confirmation.text
    return doc_id


def test_wizard_full_flow(client, pdf_bytes, complete_preliminary) -> None:
    doc_id = _upload(client, pdf_bytes)
    dmrl = [
        {
            "Arbo": "1",
            "DMC": "DMC-PUMP-A-00-00-00-00A-040A-D",
            "Titre": "Description",
            "Type": "Descriptif",
        },
        {
            "Arbo": "2",
            "DMC": "DMC-PUMP-A-00-00-00-00A-520A-D",
            "Titre": "Removal Procedure",
            "Type": "Procedure",
        },
    ]
    response = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("DMRL.json", json.dumps(dmrl).encode())},
    )
    assert response.status_code == 200, response.text

    # start -> validation de la DMRL -> etape split
    st = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert st["step"] == "dmrl"
    st = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert st["step"] == "split"

    # re-decouper par chapitre -> 2 DMs (Description + Removal Procedure)
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"split_level": "chapter"},
    ).json()
    assert len(st["dms"]) == 2

    # La DMRL fournit les types ; seule la validation du decoupage reste a faire.
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance",
        json={"split_level": "chapter"},
    ).json()
    assert st["step"] == "preliminary"
    types = {d["title"]: d["dm_type"] for d in st["dms"]}
    assert types == {"Description": "descriptive", "Removal Procedure": "procedural"}

    st = complete_preliminary(doc_id, st)
    assert st["step"] == "generate"

    # chaque DM a un XML bien forme ; le DM procedural -> <procedure>
    proc_found = False
    for d in st["dms"]:
        xml = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{d['dm_id']}/xml").text
        xml_safe.fromstring(xml, allow_internal_dtd=True)
        if d["dm_type"] == "procedural":
            assert "<procedure>" in xml
            proc_found = True
        else:
            assert "<levelledPara" in xml
    assert proc_found, types

    # ZIP de tous les DMs
    z = client.get(f"/api/v1/documents/{doc_id}/wizard/zip")
    assert z.status_code == 200
    assert z.headers["content-type"] == "application/zip"


def test_xsd_invalid_wizard_dms_are_warned_but_downloadable(client, pdf_bytes, complete_preliminary) -> None:
    doc_id = _upload(client, pdf_bytes)
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance",
        json={"split_level": "chapter"},
    ).json()
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance", json={"types": {}}
    ).json()
    dm = next(item for item in state["dms"] if item["dm_type"] == "descriptive")
    node = next(iter(dm["tree"].get("children") or []), None)
    assert node is not None
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance",
        json={"overrides": [{
            "dm_id": dm["dm_id"],
            "node_id": node["id"],
            "element": "proceduralStep",
        }]},
    ).json()

    state = complete_preliminary(doc_id, state)
    assert state["step"] == "generate"
    invalid_dm = next(item for item in state["dms"] if not item["xsd_valid"])
    assert any(violation["rule"] == "XSD" for violation in invalid_dm["xsd_violations"])
    assert any("proceduralStep" in violation["message"] for violation in invalid_dm["xsd_violations"])
    assert invalid_dm["missing_fields"]
    assert client.get(f"/api/v1/documents/{doc_id}").json()["status"] == "incomplete"

    dm_download = client.get(
        f"/api/v1/documents/{doc_id}/wizard/dm/{invalid_dm['dm_id']}/xml"
    )
    zip_download = client.get(f"/api/v1/documents/{doc_id}/wizard/zip")

    assert dm_download.status_code == 200
    assert dm_download.text.startswith("<?xml")
    assert "proceduralStep" not in dm_download.text
    assert zip_download.status_code == 200
    assert zip_download.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(zip_download.content)) as archive:
        xml_names = [name for name in archive.namelist() if name.endswith(".xml")]
        assert xml_names
        invalid_name = next(
            name for name in xml_names
            if name in {f"{invalid_dm['dm_id']}.xml", f"{invalid_dm.get('dmc')}.xml"}
        )
        assert "proceduralStep" not in archive.read(invalid_name).decode("utf-8")


def test_wizard_zip_includes_pmc_in_pmc_directory(client, pdf_bytes, complete_preliminary) -> None:
    doc_id = _upload(client, pdf_bytes)
    dmrl = [
        {
            "Arbo": "1",
            "DMC": "DMC-PUMP-A-00-00-00-00A-040A-D",
            "Titre": "Description",
            "Type": "Descriptif",
        },
        {
            "Arbo": "2",
            "DMC": "DMC-PUMP-A-00-00-00-00A-520A-D",
            "Titre": "Removal Procedure",
            "Type": "Procedure",
        },
    ]
    response = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("DMRL.json", json.dumps(dmrl).encode())},
    )
    assert response.status_code == 200, response.text

    detection_response = client.post(f"/api/v1/documents/{doc_id}/pdf-cut/detect")
    assert detection_response.status_code == 200, detection_response.text
    detection = detection_response.json()
    if detection["validation_required"] and (
        detection["selected_page"] is None or detection["selected_end_page"] is None
    ):
        confirmed = client.post(
            f"/api/v1/documents/{doc_id}/pdf-cut/confirm",
            json={
                "start_page": detection["selected_page"] or detection["default_start_page"],
                "end_page": detection["selected_end_page"] or detection["total_pages"],
            },
        )
        assert confirmed.status_code == 200, confirmed.text

    start_response = client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    assert start_response.status_code == 200, start_response.text
    state = start_response.json()
    assert state["step"] == "dmrl"
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["step"] == "split"
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["step"] == "preliminary"
    state = complete_preliminary(doc_id, state)
    assert state["step"] == "generate"

    archive_response = client.get(
        f"/api/v1/documents/{doc_id}/wizard/zip",
        params={"max_dimension": "64", "image_format": "png"},
    )
    assert archive_response.status_code == 200, archive_response.text
    pmc_path = f"PMC/{doc_id}_pmc.xml"
    with ZipFile(BytesIO(archive_response.content)) as archive:
        assert pmc_path in archive.namelist()
        assert archive.read(pmc_path) == client.get(
            f"/api/v1/documents/{doc_id}/pmc"
        ).content


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
                    "dmc": "DMC-WEG-A-00-00-00-00A-040A-D",
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
                    "dmc": "DMC-WEG-A-00-00-00-00A-040A-D",
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
            dmrl_json=json.dumps([
                {"dmc": "DMC-WEG-A-00-00-00-00A-040A-D", "title": "First"},
            ]),
        )
        db.add(doc)
        db.commit()
        doc_id = doc.id

    first = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/dm1/xml")
    second = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/dm2/xml")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert 'id="fig-0001"' in first.text
    assert 'id="fig-0001"' in second.text
    assert 'id="tab-0001"' in second.text


def test_dm_xml_recomputes_stale_template_warning_from_current_tree() -> None:
    from app.core import wizard as wizard_core
    from app.db.models import Document

    dmc = "DMC-WEG-A-00-00-00-00A-040A-D"
    root = IRNode(id="root", kind="section", level=0, children=[
        IRNode(
            id="foundations",
            kind="section",
            level=1,
            text="FONDATIONS",
            children=[IRNode(
                id="foundation-text",
                kind="paragraph",
                text="La fondation assure la stabilité du moteur.",
            )],
        ),
    ])
    stale_dm = {
        "dm_id": "dm1",
        "title": "Fondation",
        "dm_type": "descriptive",
        "dmc": dmc,
        "tree": to_dict(root),
        "template_missing_fields": ["description"],
        "missing_fields": ["description"],
        "violations": [{
            "severity": "warning",
            "rule": "TEMPLATE",
            "message": "Rubrique obligatoire du template vide : description",
            "path": "/",
        }],
    }
    doc = Document(
        s1000d_issue="4.2",
        dmrl_json=json.dumps([{"dmc": dmc, "title": "Fondation"}]),
        dms_json=json.dumps([stale_dm]),
    )

    xml = wizard_core.dm_xml(doc, "dm1")
    refreshed = json.loads(doc.dms_json)[0]

    assert "<title>FONDATIONS</title>" in xml
    assert "A REMPLACER AVANT PUBLICATION: description" not in xml
    assert not any(field == "description" for field in refreshed["missing_fields"])
    assert any("dataHandling" in field for field in refreshed["missing_fields"])
    assert refreshed["template_missing_fields"] == []
    assert not [v for v in refreshed["violations"] if v["rule"] == "TEMPLATE"]


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


def test_hide_zones_is_idempotent_after_automatic_noise_filter(client, pdf_bytes_headers) -> None:
    """Le bruit de mise en page est retire avant l'etape split.

    L'action historique « Masquer entetes/pieds » reste sans effet destructif
    et son undo conserve le meme contenu deja nettoye.
    """
    doc_id = _upload(client, pdf_bytes_headers)
    st = _split_state(client, doc_id)
    before = sum(d["node_count"] for d in st["dms"])

    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "hide_zones", "zones": ["header", "footer"]},
    ).json()
    after = sum(d["node_count"] for d in st["dms"])
    assert after == before, "le masquage manuel ne doit pas retirer du contenu deja nettoye"

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


def test_wizard_type_override(client, pdf_bytes, complete_preliminary) -> None:
    doc_id = _upload(client, pdf_bytes)
    dmrl = [
        {"DMC": "DMC-WEG-A-00-00-00-00A-040A-D", "Titre": "Description"},
        {"DMC": "DMC-WEG-A-00-00-00-00A-520A-D", "Titre": "Removal Procedure"},
    ]
    response = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("DMRL.json", json.dumps(dmrl).encode())},
    )
    assert response.status_code == 200, response.text
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert state["step"] == "dmrl"
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/update", json={
        "op": "set_type", "index": 0, "dm_type": "procedural",
    }).json()
    assert state["dmrl"][0]["dm_type"] == "procedural"
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    st = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance", json={"split_level": "chapter"}
    ).json()
    assert st["step"] == "preliminary"
    # Le type choisi dans la DMRL pilote directement le DM genere.
    dm0 = st["dms"][0]["dm_id"]
    complete_preliminary(doc_id, st)
    xml = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{dm0}/xml").text
    assert "<procedure>" in xml


def test_manual_dm_type_is_applied_before_resolution() -> None:
    from app.core import ir as ir_mod
    from app.core import wizard as wizard_core
    from app.db.models import Document

    root = IRNode(
        id="root",
        kind="section",
        children=[IRNode(id="p1", kind="paragraph", text="Check the pump.")],
    )
    doc = Document(dms_json=json.dumps([{
        "dm_id": "dm1",
        "title": "Pump",
        "dm_type": "descriptive",
        "tree": to_dict(root),
    }]))

    wizard_core._apply_types(doc, {"dm1": "procedural"})
    wizard_core._resolve_all(doc)

    tree = ir_mod.from_dict(json.loads(doc.dms_json)[0]["tree"])
    paragraph = ir_mod.find_node(tree, "p1")
    assert paragraph is not None
    assert paragraph.context == "procedural"
    assert paragraph.candidates[0].element == "proceduralStep"


def test_wizard_splits_inline_numbered_actions_after_procedural_type_selection() -> None:
    from app.core import ir as ir_mod
    from app.core import wizard as wizard_core
    from app.db.models import Document

    root = IRNode(id="root", kind="section", children=[IRNode(
        id="section",
        kind="section",
        level=4,
        text="Procédures de mise en position verticale des moteurs W22",
        children=[IRNode(
            id="paragraph",
            kind="paragraph",
            text=(
                "Pour mettre les moteurs W22 en position verticale, procédez "
                "comme suit : 1. Serrer les anneaux de levage ; "
                "2. Retirer le moteur de l’emballage."
            ),
        )],
    )])
    doc = Document(dms_json=json.dumps([{
        "dm_id": "dm1",
        "title": "Procédures W22",
        "dm_type": "descriptive",
        "tree": to_dict(root),
    }]))

    wizard_core._apply_types(doc, {"dm1": "procedural"})
    wizard_core._resolve_all(doc)

    generated = ir_mod.from_dict(json.loads(doc.dms_json)[0]["tree"])
    split_paragraph = ir_mod.find_node(generated, "paragraph")
    assert split_paragraph is not None
    assert split_paragraph.kind == "section"
    assert split_paragraph.children[0].text.endswith("comme suit :")
    actions = split_paragraph.children[1]
    assert actions.kind == "item-sequence"
    assert [item.text for item in actions.children] == [
        "Serrer les anneaux de levage",
        "Retirer le moteur de l’emballage.",
    ]

    from app.core.s1000d_schema import validate_xsd
    from app.core.s1000d_serializer import serialize

    xml = serialize(
        generated,
        issue="4.2",
        dm_type="procedural",
        title="Procédures W22",
        dm_metadata={"dmc": "DMC-WEG-A-00-00-00-00A-520A-D"},
    )
    violations = validate_xsd(
        xml, "4.2", dm_type="procedural", allow_internal_dtd=True,
    )
    assert not [violation for violation in violations if violation["severity"] == "error"], violations
    xml_root = xml_safe.fromstring(xml, allow_internal_dtd=True)
    main = xml_root.find("./content/procedure/mainProcedure")
    assert main is not None
    procedure_step = main.find("./proceduralStep")
    assert procedure_step is not None
    assert procedure_step.findtext("./title") == "Procédures de mise en position verticale des moteurs W22"
    assert "procédez comme suit" in "".join(procedure_step.find("./para").itertext())
    generated_steps = procedure_step.findall("./proceduralStep")
    assert len(generated_steps) == 2
    assert "Serrer les anneaux" in "".join(generated_steps[0].itertext())
    assert "Retirer le moteur" in "".join(generated_steps[1].itertext())
