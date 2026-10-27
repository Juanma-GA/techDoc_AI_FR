"""Synthetic procedural authoring cases, not document-specific keyword matches."""

import json
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.core import context_classifier, preliminary_detection, preliminary_review, resolver, xml_safe
from app.core.errors import AppError
from app.core.ir import IRNode, to_dict
from app.core.preliminary_detection import is_reviewable, passages
from app.core.preliminary_projection import reviewed_root
from app.core.procedure_semantics import heading_scope, heading_text, resource_rows
from app.core.procedure_structure import procedure_steps
from app.core.s1000d_schema import validate_xsd
from app.core.s1000d_serializer import SerializationDiagnostics, serialize
from app.db.models import Document
from app.db.session import SessionLocal


def procedure_tree() -> IRNode:
    tree = IRNode(id="root", kind="section", children=[
        IRNode(id="general", kind="section", text="1 General information", children=[
            IRNode(id="applicability", kind="paragraph", text="This task applies to the synthetic assembly."),
        ]),
        IRNode(id="preliminary", kind="section", text="2 Preliminary requirements", children=[
            IRNode(id="conditions", kind="section", text="2.1 Required conditions", children=[
                IRNode(id="power", kind="paragraph", text="The power supply is isolated."),
            ]),
            IRNode(id="tools", kind="section", text="2.2 Tools required", children=[
                IRNode(id="resources", kind="table", table_rows=[
                    ["Tool", "Part number", "CAGE", "Qty", "Unit", "Rating"],
                    ["Safety lock", "LOCK-3.2", "D1234", "2", "ea", "24 V"],
                ]),
            ]),
            IRNode(id="safety", kind="section", text="2.3 Safety", children=[
                IRNode(id="general-warning", kind="admonition", admonition="warning",
                       text="Wear protective gloves before starting this task."),
            ]),
        ]),
        IRNode(id="main", kind="section", text="3 Main procedure", children=[
            IRNode(id="tighten", kind="paragraph", text="Use the wrench to tighten the bolt to 12 N m."),
            IRNode(id="local-caution", kind="admonition", admonition="caution",
                   text="The hot tool can cause burns."),
            IRNode(id="grease", kind="paragraph", text="Apply grease to the seal and connect the 24 V supply."),
        ]),
        IRNode(id="closing", kind="section", text="4 Closing requirements", children=[
            IRNode(id="final-state", kind="paragraph", text="The access panel is closed."),
        ]),
    ])
    context_classifier.apply_dm_type(tree, "procedural")
    resolver.resolve(tree)
    return tree


def reviewed_document(tree: IRNode, issue: str, tmp_path) -> Document:
    document = Document(
        filename="synthetic.docx", source_format="docx", storage_path=str(tmp_path / "unused.docx"),
        s1000d_issue=issue, wizard_step="preliminary",
        status="wizard",
        dms_json=json.dumps([{
            "dm_id": "proc", "dm_type": "procedural", "title": "Synthetic maintenance", "tree": to_dict(tree),
        }]),
    )
    preliminary_review.prepare(document)
    state = preliminary_review.load(document)
    review = state["reviews"]["proc"]
    for passage in review["passages"]:
        if is_reviewable(passage):
            assert passage["suggested"] != "review"
            passage["decision"] = passage["suggested"]
    review["status"] = "reviewed"
    document.preliminary_review_json = json.dumps(state)
    return document


def test_headings_and_table_headers_are_not_requirements_but_remain_source_anchors():
    tree = procedure_tree()
    source = to_dict(tree)
    items = passages(source, source_format="pdf", page_offset=0)
    by_node = {item["node_id"]: item for item in items if item["row"] is None}
    for node_id in ("general", "preliminary", "conditions", "tools", "safety", "main", "closing"):
        assert by_node[node_id]["role"] == "heading"
        assert not is_reviewable(by_node[node_id])
        assert by_node[node_id]["decision"] is None
    header, resource = [item for item in items if item["node_id"] == "resources"]
    assert header["role"] == "table-header"
    assert resource["suggested"] == "support"
    assert resource["rule"] == "heading"
    assert resource["source_text"] == "Safety lock | LOCK-3.2 | D1234 | 2 | ea | 24 V"
    assert by_node["tighten"]["suggested"] == by_node["grease"]["suggested"] == "body"
    assert by_node["local-caution"]["suggested"] == "body"
    assert by_node["general-warning"]["suggested"] == "safety"
    assert by_node["final-state"]["suggested"] == "closing"
    assert by_node["applicability"]["suggested"] == "common"
    assert to_dict(tree) == source


@pytest.mark.parametrize("text", ["1.5", "24 V", "12 N m", "2", "LOCK-3.2", "1.5 mm"])
def test_technical_values_are_not_silently_discarded_as_chapter_numbers(text):
    tree = IRNode(id="root", kind="section", children=[
        IRNode(id="value", kind="paragraph", text=text),
    ])
    item = passages(to_dict(tree), source_format="docx", page_offset=0)[0]
    assert is_reviewable(item)
    assert item["source_text"] == text


@pytest.mark.parametrize("title, expected", [
    ("3.2 Conditions préalables", ("preliminary", "conditions")),
    ("3.3 Outillage", ("preliminary", "support")),
    ("4 Closing requirements", ("closing", None)),
    ("5 Conditions finales", ("closing", None)),
    ("6.2 Apply grease to the tool", ("unknown", None)),
])
def test_heading_context_requires_a_heading_label_not_any_resource_word(title, expected):
    assert heading_scope(title) == expected


@pytest.mark.parametrize("heading", ["24 V supply", "2-way valve", "4-stroke engine", "2024 revision"])
def test_numeric_technical_heading_is_preserved(heading):
    assert heading_text(heading) == heading


@pytest.mark.parametrize("heading", ["3.2", "3.2.", "Chapter 3.2"])
def test_number_only_heading_does_not_create_an_artificial_procedure_step(heading):
    root = IRNode(id="root", kind="section", children=[
        IRNode(id="number", kind="section", text=heading, children=[
            IRNode(id="action", kind="paragraph", text="Connect the 24 V supply."),
        ]),
    ])
    context_classifier.apply_dm_type(root, "procedural")
    resolver.resolve(root)
    xml = serialize(root, issue="4.2", dm_type="procedural")
    document = xml_safe.fromstring(xml, allow_internal_dtd=True)
    assert len(document.findall(".//mainProcedure/proceduralStep")) == 1
    assert document.find(".//mainProcedure//title") is None
    assert "Connect the 24 V supply." in "".join(document.find(".//mainProcedure").itertext())


def test_technical_number_in_a_procedure_title_survives_xml():
    root = IRNode(id="root", kind="section", children=[
        IRNode(id="step", kind="section", text="24 V supply", children=[
            IRNode(id="action", kind="paragraph", text="Connect the supply."),
        ]),
    ])
    context_classifier.apply_dm_type(root, "procedural")
    resolver.resolve(root)
    xml = serialize(root, issue="4.2", dm_type="procedural")
    assert xml_safe.fromstring(xml, allow_internal_dtd=True).findtext(
        ".//mainProcedure/proceduralStep/title",
    ) == "24 V supply"


@pytest.mark.parametrize("issue", ["4.1", "4.2"])
@pytest.mark.parametrize("reviewed", [False, True])
def test_procedural_sections_resources_and_local_warnings_survive_valid_xml(issue, reviewed, tmp_path):
    tree = procedure_tree()
    source_tree = tree
    before = to_dict(tree)
    if reviewed:
        document = reviewed_document(tree, issue, tmp_path)
        original_json = document.dms_json
        tree = reviewed_root(document, json.loads(document.dms_json)[0], tree)
        preliminary_review.require_complete(document)
        assert document.dms_json == original_json
    diagnostics = SerializationDiagnostics()
    xml = serialize(tree, issue=issue, dm_type="procedural", diagnostics=diagnostics)
    result = xml_safe.fromstring(xml, allow_internal_dtd=True)
    procedure = result.find("./content/procedure")
    assert [element.tag for element in procedure] == [
        "commonInfo", "preliminaryRqmts", "mainProcedure", "closeRqmts",
    ]
    assert procedure.findtext("./preliminaryRqmts/reqCondGroup/reqCondNoRef/reqCond") == "The power supply is isolated."
    assert "This task applies" in "".join(procedure.find("commonInfo").itertext())
    resource = procedure.find("./preliminaryRqmts/reqSupportEquips/supportEquipDescrGroup/supportEquipDescr")
    assert resource.findtext("name") == "Safety lock"
    assert resource.findtext("identNumber/partAndSerialNumber/partNumber") == "LOCK-3.2"
    assert resource.findtext("identNumber/manufacturerCode") == "D1234"
    assert resource.findtext("reqQuantity") == "2"
    assert resource.find("reqQuantity").get("unitOfMeasure") == "ea"
    assert resource.findtext("remarks/simplePara") == "Rating: 24 V"
    assert len(procedure.findall(".//supportEquipDescr")) == 1
    assert procedure.findtext("./closeRqmts/reqCondGroup/reqCondNoRef/reqCond") == "The access panel is closed."
    assert procedure.find("./preliminaryRqmts/productionMaintData") is None
    main = procedure.find("mainProcedure")
    assert len(main.findall("proceduralStep")) == 2
    assert main.find("proceduralStep[2]/caution") is not None
    assert main.find("proceduralStep[1]/caution") is None
    assert "12 N m" in "".join(main.itertext())
    assert "24 V" in "".join(main.itertext())
    assert "The hot tool can cause burns." not in "".join(procedure.find("preliminaryRqmts").itertext())
    assert not any(
        phrase in "".join(procedure.find("preliminaryRqmts").itertext())
        for phrase in ("2.1 Required conditions", "2.2 Tools required", "Tool | Part number")
    )
    assert [violation for violation in validate_xsd(
        xml, issue, dm_type="procedural", allow_internal_dtd=True,
    ) if violation["severity"] == "error"] == []
    assert diagnostics.xsd_violations == []
    assert to_dict(source_tree) == before


def test_warning_without_an_action_is_an_explicit_error_not_silently_pruned():
    with pytest.raises(AppError) as error:
        procedure_steps([IRNode(id="warning", kind="admonition", admonition="warning", text="Risk.")])
    assert error.value.code == "PROCEDURE_ACTION_REQUIRED"


def test_old_rule_versions_become_stale_without_erasing_decisions(monkeypatch, tmp_path):
    document = reviewed_document(procedure_tree(), "4.2", tmp_path)
    original = document.preliminary_review_json
    monkeypatch.setattr(preliminary_detection, "RULE_VERSION", preliminary_detection.RULE_VERSION + 1)
    assert preliminary_review.view(document)["reviews"]["proc"]["status"] == "stale"
    assert document.preliminary_review_json == original
    with pytest.raises(AppError) as error:
        preliminary_review.require_complete(document)
    assert error.value.code == "PRELIMINARY_REVIEW_REQUIRED"


def test_split_table_rows_project_only_the_reviewed_spans_not_two_full_resources(tmp_path):
    tree = procedure_tree()
    document = reviewed_document(tree, "4.2", tmp_path)
    state = preliminary_review.load(document)
    items = state["reviews"]["proc"]["passages"]
    row = next(item for item in items if item["node_id"] == "resources" and item["row"] == 1)
    split = len("Safety lock")
    pieces = [
        {**row, "id": f"piece-{start}", "start": start, "end": end,
         "source_text": row["source_text"][start:end], "text": row["source_text"][start:end]}
        for start, end in ((0, split), (split, len(row["source_text"])))
    ]
    index = items.index(row)
    items[index:index + 1] = pieces
    document.preliminary_review_json = json.dumps(state)
    projected = reviewed_root(document, json.loads(document.dms_json)[0], tree)
    resources = resource_rows(projected.reviewed_requirements["support"])
    assert [resource.name for resource in resources] == [piece["text"].strip() for piece in pieces]
    assert all(resource.quantity is None for resource in resources)


def test_structure_is_read_only_but_does_not_block_completed_review(client, tmp_path):
    document = reviewed_document(procedure_tree(), "4.2", tmp_path)
    with SessionLocal() as db:
        db.add(document)
        db.commit()
        doc_id = document.id
        revision = preliminary_review.load(document)["revision"]
    for passage_id, op in (("tools:text:0", "decide"), ("resources:0:0", "split")):
        response = client.post(f"/api/v1/documents/{doc_id}/wizard/preliminary", json={
            "revision": revision, "dm_id": "proc", "op": op, "passage_id": passage_id,
            "destination": "support", "split_at": 4,
        })
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "REVIEW_STRUCTURE_ONLY"
    done = client.post(f"/api/v1/documents/{doc_id}/wizard/preliminary", json={
        "revision": revision, "dm_id": "proc", "op": "complete", "confirm_empty": True,
    })
    assert done.status_code == 200, done.text
    assert done.json()["reviews"]["proc"]["status"] == "reviewed"
    assert all(
        passage["decision"] is None
        for passage in done.json()["reviews"]["proc"]["passages"] if not is_reviewable(passage)
    )


def test_splitting_closing_conditions_retains_context_and_requires_new_decisions(client, tmp_path):
    document = reviewed_document(procedure_tree(), "4.2", tmp_path)
    with SessionLocal() as db:
        db.add(document)
        db.commit()
        doc_id = document.id
        revision = preliminary_review.load(document)["revision"]
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/preliminary", json={
        "revision": revision, "dm_id": "proc", "op": "split",
        "passage_id": "final-state:text:0", "split_at": 10,
    })
    assert response.status_code == 200, response.text
    review = response.json()["reviews"]["proc"]
    parts = [passage for passage in review["passages"] if passage["node_id"] == "final-state"]
    assert [part["suggested"] for part in parts] == ["closing", "closing"]
    assert all(part["decision"] is None for part in parts)
    assert "".join(part["source_text"] for part in parts) == "The access panel is closed."
    assert review["status"] == "pending"


@pytest.mark.parametrize("issue", ["4.1", "4.2"])
def test_common_closing_and_resources_are_identical_in_xml_and_zip(client, tmp_path, issue):
    from docx import Document as WordDocument

    source = WordDocument()
    source.add_paragraph("Synthetic maintenance source.")
    source.save(str(tmp_path / "unused.docx"))
    document = reviewed_document(procedure_tree(), issue, tmp_path)
    with SessionLocal() as db:
        db.add(document)
        db.commit()
        doc_id = document.id
        original_tree = json.loads(document.dms_json)[0]["tree"]
    generated = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert generated.status_code == 200, generated.text
    assert generated.json()["step"] == "generate"
    assert generated.json()["dms"][0]["xsd_valid"]
    single = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/proc/xml")
    assert single.status_code == 200, single.text
    xml = xml_safe.fromstring(single.content, allow_internal_dtd=True)
    assert xml.findtext(".//closeRqmts/reqCondGroup/reqCondNoRef/reqCond") == "The access panel is closed."
    assert xml.findtext(".//supportEquipDescr/reqQuantity") == "2"
    assert xml.find(".//commonInfo") is not None
    assert xml.find(".//productionMaintData") is None
    download = client.get(f"/api/v1/documents/{doc_id}/wizard/zip")
    assert download.status_code == 200, download.text
    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.read("proc.xml") == single.content
    with SessionLocal() as db:
        assert json.loads(db.get(Document, doc_id).dms_json)[0]["tree"] == original_tree
