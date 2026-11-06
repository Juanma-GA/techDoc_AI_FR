"""Synthetic reference procedures, persistence, decisions and export gates."""

import json
from io import BytesIO
from zipfile import ZipFile

import pymupdf as fitz
import pytest

from app.core import context_classifier, resolver
from app.core import preliminary_review as review
from app.core.ir import IRNode, to_dict
from app.core.preliminary_detection import passages
from app.core.procedure_template import apply_template, clear_template_applications
from app.db.models import Document
from app.db.session import SessionLocal


@pytest.fixture(params=["4.1", "4.2"])
def procedure(client, tmp_path, request):
    source = tmp_path / "synthetic.pdf"
    texts = [
        "Ensure the power is off.",
        "Two qualified technicians.",
        "Required tools: torque wrench.",
        "Consumables: grease.",
        "Spare parts: new gasket.",
        "WARNING: Wear protective gloves.",
        "Disconnect the connector.",
    ]
    with fitz.open() as pdf:
        for index in range(4):
            page = pdf.new_page()
            for row, text in enumerate(texts):
                page.insert_text((72, 72 + row * 24), text)
        pdf.save(str(source))
    tree = IRNode(id="root", kind="section", children=[
        IRNode(id=f"p{index}", kind="paragraph", text=text, page=1 + index % 2)
        for index, text in enumerate(texts)
    ] + [
        IRNode(id="table", kind="table", page=2,
               table_rows=[["Tool", "Qty"], ["Screwdriver", "1"]]),
    ])
    context_classifier.apply_dm_type(tree, "procedural")
    resolver.resolve(tree)
    with SessionLocal() as db:
        doc = Document(
            filename=source.name, source_format="pdf", storage_path=str(source),
            s1000d_issue=request.param, wizard_step="structure", status="wizard",
            pdf_cut_path=str(source), pdf_cut_start_page=2, pdf_cut_end_page=3,
            dms_json=json.dumps([{
                "dm_id": "proc", "dm_type": "procedural", "title": "Removal",
                "tree": to_dict(tree),
            }, {
                "dm_id": "desc", "dm_type": "descriptive", "title": "Overview",
                "tree": to_dict(IRNode(id="d", kind="section", children=[
                    IRNode(id="dp", kind="paragraph", text="A descriptive body."),
                ])),
            }]),
        )
        db.add(doc)
        db.commit()
        doc_id = doc.id
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert response.status_code == 200, response.text
    assert response.json()["step"] == "preliminary"
    return doc_id, source


def _action(client, doc_id, **kwargs):
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]
    return client.post(
        f"/api/v1/documents/{doc_id}/wizard/preliminary",
        json={"revision": state["revision"], "dm_id": "proc", **kwargs},
    )


def _finish(client, doc_id):
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]
    for passage in state["reviews"]["proc"]["passages"]:
        if passage.get("role", "content") != "content":
            continue
        response = _action(
            client, doc_id, op="decide", passage_id=passage["id"],
            destination=passage["suggested"] if passage["suggested"] != "review" else "body",
        )
        assert response.status_code == 200, response.text
    done = _action(client, doc_id, op="complete", confirm_empty=True)
    assert done.status_code == 200, done.text


def test_first_procedure_template_matches_only_identical_source_markers():
    def passage(text, *, marker_key=None, decision=None, target_tag=None, suggested="support",
                rule="heading"):
        return {
            "phase": "preliminary", "category_hint": "support", "suggested": suggested,
            "rule": rule, "kind": "paragraph", "role": "content", "admonition": None,
            "text": text, "source_text": text, "decision": decision, "target_tag": target_tag,
            "marker_key": marker_key,
        }

    source = {"passages": [
        passage(
            "Part number: LOCK-3.2", marker_key="part number",
            decision="support", target_tag="partNumber",
            rule="part-number",
        ),
        passage("Tool name: wrench", marker_key="tool details", decision="support", target_tag="name"),
        passage("Tool part: W-10", marker_key="tool details", decision="support", target_tag="partNumber"),
        passage(
            "Aucun outil requis.", marker_key="empty tools",
            decision="support", target_tag="noSupportEquips",
            rule="explicit-none",
        ),
    ]}
    target = {"passages": [
        passage("Part number: LOCK-9", marker_key="part number", target_tag=None, rule="part-number"),
        passage("Another tool", marker_key="tool details", target_tag=None),
        passage("A torque wrench is required.", marker_key="empty tools", target_tag=None,
                rule="explicit-none"),
        passage("Use the tool.", decision="body", target_tag="proceduralStep",
                suggested="body", marker_key=None),
    ]}

    assert apply_template(source, target, source_dm_id="first", saved_at="now") == 1
    assert target["passages"][0]["decision"] == "support"
    assert target["passages"][0]["target_tag"] == "partNumber"
    assert target["passages"][0]["template_source_dm_id"] == "first"
    assert target["passages"][1]["decision"] is None
    assert target["passages"][2]["decision"] is None
    assert target["status"] == "pending"
    assert target["partial"] is True

    clear_template_applications({"reviews": {"second": target}}, "first")
    assert target["passages"][0]["decision"] is None
    assert target["passages"][0]["target_tag"] is None
    assert "template_source_dm_id" not in target["passages"][0]
    assert target["passages"][3]["decision"] == "body"


def test_first_procedure_template_reuses_choices_from_cell_titles():
    def review_for(dm_id: str, values: list[str]) -> dict:
        tree = IRNode(id=f"{dm_id}-root", kind="section", children=[
            IRNode(id=f"{dm_id}-table", kind="table", table_rows=[
                ["Description", "REQUIRED PERSON(S)"],
                values,
            ]),
        ])
        return {
            "passages": passages(to_dict(tree), source_format="docx", page_offset=0),
        }

    source = review_for("first", ["Safety lock", "2 OPER"])
    target = review_for("second", ["Torque wrench", "1 OPER"])
    source_headers = [item for item in source["passages"] if item["row"] == 0]
    source_values = [item for item in source["passages"] if item["row"] == 1]

    assert all(item["role"] == "table-header" for item in source_headers)
    assert [item["source_text"] for item in source_values] == ["Safety lock", "2 OPER"]
    assert [item["marker_key"] for item in source_values] == ["description", "required person s"]
    assert source_values[1]["detector_title"] == "REQUIRED PERSON(S)"
    source_values[0].update(decision="support", target_tag="name")
    source_values[1].update(decision="personnel", target_tag="personnel")

    assert apply_template(source, target, source_dm_id="first", saved_at="now") == 2
    target_values = [item for item in target["passages"] if item["row"] == 1]
    assert [(item["decision"], item["target_tag"]) for item in target_values] == [
        ("support", "name"),
        ("personnel", "personnel"),
    ]


def test_completing_first_procedure_applies_its_tag_to_matching_procedures(tmp_path):
    dms = []
    for dm_id in ("first", "second"):
        root = IRNode(id=f"{dm_id}-root", kind="section", children=[
            IRNode(id=f"{dm_id}-table", kind="table", table_rows=[
                ["REQUIRED PERSON(S)"], ["1 OPER"],
            ]),
        ])
        context_classifier.apply_dm_type(root, "procedural")
        resolver.resolve(root)
        dms.append({
            "dm_id": dm_id, "dm_type": "procedural", "title": "Synthetic procedure",
            "tree": to_dict(root),
        })

    with SessionLocal() as db:
        document = Document(
            filename="synthetic.docx", source_format="docx",
            storage_path=str(tmp_path / "synthetic.docx"), s1000d_issue="4.2",
            wizard_step="preliminary", status="wizard", dms_json=json.dumps(dms),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        review.prepare(document)
        db.commit()
        state = review.load(document)
        source_passage = next(
            passage for passage in state["reviews"]["first"]["passages"]
            if passage["role"] == "content"
        )

        updated = review.apply(db, document, review.ReviewAction(
            revision=state["revision"], dm_id="first", op="decide",
            passage_id=source_passage["id"], destination="personnel", target_tag="personnel",
            detector_title="REQUIRED PERSON(S)",
        ))
        configured = next(
            passage for passage in updated["reviews"]["first"]["passages"]
            if passage["id"] == source_passage["id"]
        )
        assert configured["text"] == "1 OPER"
        assert configured["detector_title"] == "REQUIRED PERSON(S)"
        completed = review.apply(db, document, review.ReviewAction(
            revision=updated["revision"], dm_id="first", op="complete", confirm_empty=True,
        ))

    inherited = next(
        passage for passage in completed["reviews"]["second"]["passages"]
        if passage["role"] == "content"
    )
    assert completed["template_dm_id"] == "first"
    assert completed["reviews"]["second"]["status"] == "reviewed"
    assert inherited["decision"] == "personnel"
    assert inherited["target_tag"] == "personnel"
    assert inherited["detector_title"] == "REQUIRED PERSON(S)"
    assert inherited["template_source_dm_id"] == "first"


def test_completing_template_rebuilds_unfinished_reviews_and_preserves_verified_ones(tmp_path):
    dm_ids = ("first", "partial", "verified", "skipped", "stale", "missing")
    dms = []
    for dm_id in dm_ids:
        root = IRNode(id=f"{dm_id}-root", kind="section", children=[
            IRNode(id=f"{dm_id}-table", kind="table", table_rows=[
                ["REQUIRED PERSON(S)"], ["1 OPER"],
            ]),
        ])
        context_classifier.apply_dm_type(root, "procedural")
        resolver.resolve(root)
        dms.append({
            "dm_id": dm_id, "dm_type": "procedural", "title": "Synthetic procedure",
            "tree": to_dict(root),
        })

    with SessionLocal() as db:
        document = Document(
            filename="synthetic.docx", source_format="docx",
            storage_path=str(tmp_path / "synthetic.docx"), s1000d_issue="4.2",
            wizard_step="preliminary", status="wizard", dms_json=json.dumps(dms),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        review.prepare(document)
        state = review.load(document)

        source_passage = next(
            passage for passage in state["reviews"]["first"]["passages"]
            if passage["role"] == "content"
        )
        partial = state["reviews"]["partial"]
        partial_passage = next(passage for passage in partial["passages"] if passage["role"] == "content")
        partial_passage.update(decision="body", target_tag="proceduralStep", text="Manual correction")
        partial["partial"] = True

        verified = state["reviews"]["verified"]
        verified_passage = next(
            passage for passage in verified["passages"] if passage["role"] == "content"
        )
        verified_passage.update(decision="body", target_tag="proceduralStep")
        verified["status"] = "reviewed"
        verified["partial"] = False
        verified["saved_at"] = "verified-before-template"
        verified_before = json.loads(json.dumps(verified))

        state["reviews"]["skipped"]["status"] = "skipped"
        state["reviews"]["stale"]["status"] = "reviewed"
        state["reviews"]["stale"]["fingerprint"] = "obsolete-fingerprint"
        del state["reviews"]["missing"]
        document.preliminary_review_json = json.dumps(state)
        db.commit()

        updated = review.apply(db, document, review.ReviewAction(
            revision=state["revision"], dm_id="first", op="decide",
            passage_id=source_passage["id"], destination="personnel", target_tag="personnel",
        ))
        completed = review.apply(db, document, review.ReviewAction(
            revision=updated["revision"], dm_id="first", op="complete", confirm_empty=True,
        ))

    assert completed["reviews"]["verified"] == verified_before
    for dm_id in ("partial", "skipped", "stale", "missing"):
        regenerated = completed["reviews"][dm_id]
        inherited = next(passage for passage in regenerated["passages"] if passage["role"] == "content")
        assert regenerated["status"] == "reviewed"
        assert regenerated["partial"] is False
        assert inherited["text"] == "1 OPER"
        assert inherited["decision"] == "personnel"
        assert inherited["target_tag"] == "personnel"
        assert inherited["template_source_dm_id"] == "first"


def test_reference_rules_cover_all_categories_and_every_source_passage(procedure, client):
    doc_id, _ = procedure
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()
    assert state["steps"] == ["split", "type", "structure", "preliminary", "generate"]
    assert set(state["preliminary"]["reviews"]) == {"proc"}
    items = state["preliminary"]["reviews"]["proc"]["passages"]
    assert len(items) == 11
    assert {p["suggested"] for p in items} >= {
        "conditions", "personnel", "support", "supplies", "spares", "safety", "body",
    }
    assert [p["suggested"] for p in items] == [
        "conditions", "personnel", "support", "supplies", "spares", "safety",
        "body", "body", "body", "support", "support",
    ]
    assert all(p["decision"] is None for p in items)
    assert items[7]["role"] == "table-header"
    assert items[0]["page"] == 2  # Original PDF page, not cut-page number.
    assert all(p["source_text"] == p["text"] for p in items)
    assert all(p["end"] - p["start"] == len(p["source_text"]) for p in items)


def test_review_rejects_a_tag_from_another_category(procedure, client):
    doc_id, _ = procedure
    items = client.get(f"/api/v1/documents/{doc_id}/wizard").json()[
        "preliminary"
    ]["reviews"]["proc"]["passages"]
    personnel = next(item for item in items if item["suggested"] == "personnel")

    response = _action(
        client, doc_id, op="decide", passage_id=personnel["id"],
        destination="personnel", target_tag="partNumber",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "REVIEW_TAG_INVALID"
    unchanged = client.get(f"/api/v1/documents/{doc_id}/wizard").json()[
        "preliminary"
    ]["reviews"]["proc"]["passages"]
    assert next(item for item in unchanged if item["id"] == personnel["id"])["decision"] is None


def test_generation_and_direct_exports_cannot_bypass_review(procedure, client):
    doc_id, _ = procedure
    assert client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).status_code == 409
    assert client.get(f"/api/v1/documents/{doc_id}/wizard/dm/proc/xml").status_code == 409
    assert client.get(f"/api/v1/documents/{doc_id}/wizard/zip").status_code == 409
    assert _action(client, doc_id, op="complete", confirm_empty=True).status_code == 409
    assert _action(client, doc_id, op="complete", confirm_empty=False).status_code == 409
    for path in ("extract", "xml"):
        response = (
            client.post(f"/api/v1/documents/{doc_id}/{path}") if path == "extract"
            else client.get(f"/api/v1/documents/{doc_id}/{path}")
        )
        assert response.status_code == 409
        assert response.json()["code"] == "WIZARD_WORKFLOW_REQUIRED"


def test_cursor_decisions_and_edits_survive_new_database_sessions(procedure, client):
    doc_id, _ = procedure
    response = _action(client, doc_id, op="decide", passage_id="p0:text:0",
                       destination="conditions", text="Power isolated.")
    assert response.status_code == 200
    response = _action(client, doc_id, op="cursor", page=3, scroll_top=1250.5,
                       selected_id="p0:text:0")
    assert response.status_code == 200
    with SessionLocal() as db:
        saved = review.view(db.get(Document, doc_id))
    current = saved["reviews"]["proc"]
    assert saved["active_dm_id"] == "proc"
    assert current["position"] == {"page": 3, "scroll_top": 1250.5, "selected_id": "p0:text:0"}
    assert current["passages"][0]["decision"] == "conditions"
    assert current["passages"][0]["text"] == "Power isolated."
    assert current["saved_at"]
    assert client.get(f"/api/v1/documents/{doc_id}/wizard").json()["step"] == "preliminary"
    response = _action(client, doc_id, op="decide", passage_id="p0:text:0", text="Power safely isolated.")
    assert response.json()["reviews"]["proc"]["passages"][0]["decision"] == "conditions"


def test_conflicting_tabs_and_invalid_input_are_rejected(procedure, client):
    doc_id, _ = procedure
    body = {"revision": 1, "dm_id": "proc", "op": "cursor", "page": 2}
    first = client.post(f"/api/v1/documents/{doc_id}/wizard/preliminary", json=body)
    assert first.status_code == 200
    second = client.post(f"/api/v1/documents/{doc_id}/wizard/preliminary", json=body)
    assert second.status_code == 409
    assert second.json()["code"] == "REVIEW_CONFLICT"
    for invalid in (
        {"op": "cursor", "page": 999},
        {"op": "cursor", "scroll_top": -1},
        {"op": "decide", "passage_id": "p0:text:0", "destination": "invented"},
        {"op": "decide", "passage_id": "p0:text:0", "text": "   "},
        {"op": "split", "passage_id": "p0:text:0", "split_at": 999},
    ):
        assert _action(client, doc_id, **invalid).status_code == 422


def test_split_preserves_exact_source_ranges(procedure, client):
    doc_id, _ = procedure
    response = _action(client, doc_id, op="split", passage_id="p0:text:0", split_at=11)
    assert response.status_code == 200, response.text
    items = response.json()["reviews"]["proc"]["passages"][:2]
    assert "".join(p["source_text"] for p in items) == "Ensure the power is off."
    assert [(p["start"], p["end"]) for p in items] == [(0, 11), (11, 24)]
    assert all(p["decision"] is None for p in items)
    assert len({p["id"] for p in items}) == 2
    _action(client, doc_id, op="decide", passage_id=items[0]["id"], text="Changed", destination="body")
    assert _action(client, doc_id, op="split", passage_id=items[0]["id"], split_at=2).status_code == 409


def test_changed_source_requires_explicit_restart(procedure, client):
    doc_id, source = procedure
    _finish(client, doc_id)
    with source.open("ab") as stream:
        stream.write(b"\n% Synthetic revision\n")
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]
    assert state["source_changed"]
    assert state["reviews"]["proc"]["status"] == "stale"
    assert client.get(f"/api/v1/documents/{doc_id}/wizard/dm/proc/xml").status_code == 409
    assert _action(client, doc_id, op="cursor", page=2).status_code == 409
    restarted = _action(client, doc_id, op="restart")
    assert restarted.status_code == 200
    assert all(p["decision"] is None for p in restarted.json()["reviews"]["proc"]["passages"])


def test_pdf_pages_and_exact_source_anchors(procedure, client):
    doc_id, _ = procedure
    response = client.get(f"/api/v1/documents/{doc_id}/wizard/preliminary/proc/pages")
    assert [p["page"] for p in response.json()] == [2, 3]
    response = client.get(f"/api/v1/documents/{doc_id}/wizard/preliminary/proc/page/2")
    assert response.status_code == 200, response.text
    assert response.json()["anchors"]["p0:text:0"]
    assert client.get(f"/api/v1/documents/{doc_id}/wizard/preliminary/proc/page/4").status_code == 422


def test_pdf_table_zone_api_returns_cell_rectangles(client, tmp_path):
    source = tmp_path / "synthetic-procedure-table.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page(width=600, height=300)
        xs, ys = [30, 165, 300, 400, 530], [30, 75, 120, 165]
        for x in xs:
            page.draw_line((x, ys[0]), (x, ys[-1]))
        for y in ys:
            page.draw_line((xs[0], y), (xs[-1], y))
        rows = [
            ["EQUIPMENT : SIMFADS", "", "OBJECT: CM001", ""],
            ["MAINTENANCE LEVEL(S)", "REQUIRED PERSON(S)", "TOTAL TIME", "PERIODICITY"],
            ["LEVEL 2", "1 OPER", "0.23", "UNSCHEDULED"],
        ]
        for row_index, row in enumerate(rows):
            for column, text in enumerate(row):
                if text:
                    page.insert_text((xs[column] + 4, ys[row_index] + 20), text, fontsize=8)
        pdf.save(str(source))

    from app.core.structure_infer import build_ir
    from app.parsers.pdf_parser import parse_pdf_pages

    parsed = parse_pdf_pages(source)
    tree = build_ir([block for page in parsed for block in page.blocks])
    context_classifier.apply_dm_type(tree, "procedural")
    resolver.resolve(tree)
    dm = {"dm_id": "table-procedure", "dm_type": "procedural", "title": "Synthetic",
          "tree": to_dict(tree)}
    with SessionLocal() as db:
        document = Document(
            filename=source.name, source_format="pdf", storage_path=str(source),
            s1000d_issue="4.2", wizard_step="preliminary", status="wizard",
            dms_json=json.dumps([dm]),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        review.prepare(document)
        db.commit()
        doc_id = document.id

    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]
    passages = state["reviews"]["table-procedure"]["passages"]
    zone = next(item for item in passages if item.get("source_marker") == "REQUIRED PERSON(S)")
    response = client.get(
        f"/api/v1/documents/{doc_id}/wizard/preliminary/table-procedure/page/1"
    )

    assert response.status_code == 200, response.text
    assert response.json()["anchors"][zone["id"]] == zone["anchor_rects"]
    assert len(zone["anchor_rects"]) == 2


def test_unclassified_table_rows_create_one_passage_per_cell():
    tree = {
        "id": "root",
        "kind": "section",
        "text": "",
        "children": [{
            "id": "cell-table",
            "kind": "table",
            "text": "",
            "table_rows": [["left cell", "right cell"]],
            "children": [],
        }],
    }

    items = passages(tree, source_format="docx", page_offset=0)
    cells = [item for item in items if item["role"] == "content"]

    assert [item["source_text"] for item in cells] == ["left cell", "right cell"]
    assert [item["column"] for item in cells] == [0, 1]
    assert [item["anchor_texts"] for item in cells] == [["left cell"], ["right cell"]]
    assert [item["source_cells"] for item in cells] == [
        ["left cell", "right cell"],
        ["left cell", "right cell"],
    ]


def test_decisions_drive_xml_zip_and_keep_source_immutable(procedure, client):
    doc_id, _ = procedure
    with SessionLocal() as db:
        original = json.loads(db.get(Document, doc_id).dms_json)[0]["tree"]
    _finish(client, doc_id)
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert response.status_code == 200, response.text
    assert response.json()["step"] == "generate"
    assert next(dm for dm in response.json()["dms"] if dm["dm_id"] == "proc")["xsd_valid"]
    xml = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/proc/xml")
    assert xml.status_code == 200, xml.text
    from lxml import etree
    root = etree.fromstring(xml.content)
    assert root.xpath("string(//preliminaryRqmts/reqCondGroup//reqCond)") == "Ensure the power is off."
    assert "Disconnect the connector." in root.xpath("string(//mainProcedure)")
    assert "Ensure the power is off." not in root.xpath("string(//mainProcedure)")
    assert "Screwdriver" in root.xpath("string(//reqSupportEquips)")
    download = client.get(f"/api/v1/documents/{doc_id}/wizard/zip")
    assert download.status_code == 200, download.text
    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.read("proc.xml") == xml.content
    with SessionLocal() as db:
        assert json.loads(db.get(Document, doc_id).dms_json)[0]["tree"] == original
    assert client.post(f"/api/v1/documents/{doc_id}/wizard/back").json()["step"] == "preliminary"


def test_skipping_reviews_generates_original_procedural_structure(procedure, client):
    doc_id, _ = procedure
    with SessionLocal() as db:
        original = json.loads(db.get(Document, doc_id).dms_json)[0]["tree"]

    skipped = _action(client, doc_id, op="skip")
    assert skipped.status_code == 200, skipped.text
    assert all(item["status"] == "skipped" for item in skipped.json()["reviews"].values())

    generated = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert generated.status_code == 200, generated.text
    assert generated.json()["step"] == "generate"
    with SessionLocal() as db:
        assert all(item["status"] == "skipped"
                   for item in review.view(db.get(Document, doc_id))["reviews"].values())

    xml = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/proc/xml")
    assert xml.status_code == 200, xml.text
    assert "Ensure the power is off." in xml.text
    assert "Disconnect the connector." in xml.text
    download = client.get(f"/api/v1/documents/{doc_id}/wizard/zip")
    assert download.status_code == 200, download.text
    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.read("proc.xml") == xml.content

    with SessionLocal() as db:
        assert json.loads(db.get(Document, doc_id).dms_json)[0]["tree"] == original


def test_skipping_remaining_reviews_preserves_partial_edits_and_generates(procedure, client):
    doc_id, _ = procedure
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]
    passages = [
        item for item in state["reviews"]["proc"]["passages"]
        if item.get("role", "content") == "content"
    ]
    edited = []
    for index, passage in enumerate(passages[:3]):
        text = f"Synthetic edited passage {index}."
        response = _action(
            client, doc_id, op="decide", passage_id=passage["id"],
            destination="conditions" if index == 0 else "body", text=text,
        )
        assert response.status_code == 200, response.text
        edited.append(text)

    skipped = _action(client, doc_id, op="skip")
    assert skipped.status_code == 200, skipped.text
    partial = skipped.json()["reviews"]["proc"]
    assert partial["status"] == "reviewed"
    assert partial["partial"] is True
    assert [item["text"] for item in partial["passages"] if item["text"] in edited] == edited

    generated = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert generated.status_code == 200, generated.text
    xml = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/proc/xml")
    assert xml.status_code == 200, xml.text
    for text in edited:
        assert text in xml.text
    assert "Consumables: grease." in xml.text
    assert "Disconnect the connector." in xml.text


def test_empty_review_requires_positive_confirmation_and_word_has_reading_pages(client):
    with SessionLocal() as db:
        doc = Document(filename="empty.docx", source_format="docx", storage_path="synthetic-unused",
                       s1000d_issue="4.2", wizard_step="structure", dms_json=json.dumps([{
                           "dm_id": "proc", "dm_type": "procedural", "title": "Empty",
                           "tree": to_dict(IRNode(id="empty", kind="section")),
                       }]))
        db.add(doc)
        db.commit()
        doc_id = doc.id
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["preliminary"]["reviews"]["proc"]["status"] == "pending"
    assert _action(client, doc_id, op="complete").status_code == 409
    assert _action(client, doc_id, op="complete", confirm_empty=True).status_code == 200
    items = passages(to_dict(IRNode(id="root", kind="section", children=[
        IRNode(id="a", kind="paragraph", text="A" * 2400),
        IRNode(id="b", kind="paragraph", text="B"),
    ])), source_format="docx", page_offset=0)
    assert [p["page"] for p in items] == [1, 2]


def test_compare_and_swap_rejects_a_concurrent_database_session(procedure):
    doc_id, _ = procedure
    with SessionLocal() as first, SessionLocal() as second:
        original = first.get(Document, doc_id)
        concurrent = second.get(Document, doc_id)
        revision = review.load(original)["revision"]
        action = review.ReviewAction(revision=revision, dm_id="proc", op="cursor", page=2)
        review.apply(first, original, action)
        from app.core.errors import AppError
        with pytest.raises(AppError) as error:
            review.apply(second, concurrent, action)
        assert error.value.code == "REVIEW_CONFLICT"


def test_migration_creates_review_column_only_in_a_temporary_database(tmp_path, monkeypatch):
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text

    from alembic import command
    from app.config import settings
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'migration.db'}")
    config = Config()
    config.set_main_option("script_location", "alembic")
    command.upgrade(config, "0010_resource_paths")
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO documents "
            "(id, filename, source_format, storage_path, s1000d_issue, context_hint, status, created_at) "
            "VALUES ('synthetic-existing', 'synthetic-existing.pdf', 'pdf', "
            "'synthetic-unused', '4.2', 'mixed', 'uploaded', '2026-10-27 12:00:00')"
        ))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert "preliminary_review_json" in {column["name"] for column in inspect(connection).get_columns("documents")}
        assert connection.scalar(text("SELECT filename FROM documents")) == "synthetic-existing.pdf"
    command.downgrade(config, "0010_resource_paths")
    with engine.connect() as connection:
        assert "preliminary_review_json" not in {column["name"] for column in inspect(connection).get_columns("documents")}
        assert connection.scalar(text("SELECT filename FROM documents")) == "synthetic-existing.pdf"
    engine.dispose()


def test_backtracking_to_structure_preserves_review_but_reanalysis_invalidates_it(procedure, client):
    doc_id, _ = procedure
    _finish(client, doc_id)
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/back")
    assert response.json()["step"] == "structure"
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert response.json()["preliminary"]["reviews"]["proc"]["status"] == "reviewed"
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        review.invalidate_source(doc)
        db.commit()
    assert client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]["reviews"]["proc"]["status"] == "stale"


def test_ingest_rejects_mixed_scans_without_ignoring_pages(tmp_path):
    from app.core import ingest
    from app.core.errors import AppError
    source = tmp_path / "synthetic-mixed.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "A sufficiently long synthetic text page.")
        page = pdf.new_page()
        image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20))
        image.set_rect(image.irect, (20, 20, 20))
        page.insert_image(page.rect, pixmap=image)
        pdf.new_page()  # A genuinely blank page is not an OCR failure.
        pdf.save(str(source))
    with pytest.raises(AppError) as error:
        ingest.extract_blocks(source, fmt="pdf")
    assert error.value.code == "OCR_UNAVAILABLE"
    assert error.value.detail == {"pages_in_analyzed_pdf": [2]}
