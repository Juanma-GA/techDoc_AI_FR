"""Non-regressions des deux bugs bloquants.

Bug 1 : "Unexpected Server Error" a la generation/validation.
Bug 2 : duplication des illustrations.
"""

from __future__ import annotations

import json

from app.core import xml_safe
from app.core.ir import IRNode
from app.core.s1000d_serializer import serialize
from app.core.validator import validate_document
from app.core.wizard import images_dir


def _upload(client, data: bytes, name: str = "manual.pdf") -> str:
    r = client.post(
        "/api/v1/documents",
        files={"file": (name, data)},
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


def _run_wizard(client, doc_id: str) -> dict:
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"types": {}})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"overrides": []})
    r = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert r.status_code == 200, r.text
    return r.json()


# --- Bug 1 : plus de 500 a la generation / validation -----------------------


def test_serialize_strips_control_characters() -> None:
    """Un PDF ramene des caracteres de controle (form feed, NUL) : lxml levait
    une ValueError -> 500 'Unexpected server error'."""
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="n1", kind="paragraph", text="Avant\x0c apres\x00 fin"),
        IRNode(id="n2", kind="figure", text="Figure 1\x0b legende"),
    ])
    xml = serialize(root, issue="4.2", dm_type="descriptive", title="Titre\x0c")
    xml_safe.fromstring(xml, allow_internal_dtd=True)
    assert "\x0c" not in xml and "\x00" not in xml


def test_serialize_admonition_without_candidates() -> None:
    """Une admonition non resolue (candidats vides) levait une IndexError."""
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="n1", kind="admonition", admonition="warning", text="Danger."),
    ])
    xml = serialize(root, issue="4.2", dm_type="descriptive")
    assert "<warning>" in xml


def test_serialize_rejects_invalid_element_name() -> None:
    """Un override humain fantaisiste ne doit pas faire planter la serialisation."""
    node = IRNode(id="n1", kind="paragraph", text="x")
    node.candidates = [type("C", (), {"element": "1 mauvais nom", "score": 1.0,
                                      "rationale": ""})()]
    xml = serialize(IRNode(id="r", kind="section", level=0, children=[node]),
                    issue="4.2", dm_type="descriptive")
    xml_safe.fromstring(xml, allow_internal_dtd=True)


def test_validate_document_never_raises_on_bad_brex() -> None:
    xml = serialize(IRNode(id="r", kind="section", level=0), issue="4.2", dm_type="descriptive")
    violations = validate_document(xml, issue="4.2", brex_xml="<pas-un-brex")
    assert isinstance(violations, list)


def test_wizard_generate_returns_200_on_hostile_document(client, pdf_bytes) -> None:
    state = _run_wizard(client, _upload(client, pdf_bytes))
    assert state["step"] == "generate"
    assert all(d["has_xml"] for d in state["dms"])


def test_dm_download_rebuilds_stale_persisted_xml(client, pdf_bytes, complete_preliminary) -> None:
    doc_id = _upload(client, pdf_bytes)
    dmrl = [
        {"DMC": "DMC-PUMP-A-00-00-00-00A-040A-D", "Titre": "Description"},
        {"DMC": "DMC-PUMP-A-00-00-00-00A-520A-D", "Titre": "Removal Procedure"},
    ]
    response = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("DMRL.json", json.dumps(dmrl).encode())},
    )
    assert response.status_code == 200, response.text
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/start", json={"cut_pdf": False}
    ).json()
    assert state["step"] == "dmrl"
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["step"] == "split"
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    if state["step"] == "preliminary":
        state = complete_preliminary(doc_id, state)
    assert state["step"] == "generate"

    dm_id = state["dms"][0]["dm_id"]
    from app.db.models import Document
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        document = db.get(Document, doc_id)
        dms = json.loads(document.dms_json)
        dms[0]["xml"] = "<dmodule><content>obsolete</content></dmodule>"
        document.dms_json = json.dumps(dms, ensure_ascii=False)
        db.commit()
    finally:
        db.close()

    rebuilt = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{dm_id}/xml")
    assert rebuilt.status_code == 200
    assert "obsolete" not in rebuilt.text
    assert "<!DOCTYPE dmodule [" in rebuilt.text


# --- Bug 2 : plus de duplication d'illustrations ----------------------------


def test_repeated_image_extracted_once(client, pdf_bytes_repeated_image) -> None:
    doc_id = _upload(client, pdf_bytes_repeated_image)
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    names = client.get(f"/api/v1/documents/{doc_id}/wizard/images").json()
    assert len(names) == 1, f"image dupliquee : {names}"


def test_restarting_wizard_does_not_pile_up_images(client, pdf_bytes_image) -> None:
    doc_id = _upload(client, pdf_bytes_image)
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    first = client.get(f"/api/v1/documents/{doc_id}/wizard/images").json()
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    again = client.get(f"/api/v1/documents/{doc_id}/wizard/images").json()
    assert again == first
    assert len(list(images_dir(doc_id).glob("*.jpg"))) == len(first)


def test_multiple_figure_captions_on_one_line_create_separate_figures() -> None:
    from app.core.ir import RawBlock
    from app.core.structure_infer import build_ir

    root = build_ir([RawBlock(
        text="Figure 4.1 Serrage correct Figure 4.2 Serrage incorrect Figure 4.3 Detail",
        page=1,
    )])

    assert [node.text for node in root.walk() if node.kind == "figure"] == [
        "Figure 4.1 Serrage correct",
        "Figure 4.2 Serrage incorrect",
        "Figure 4.3 Detail",
    ]


def test_numbered_note_items_continue_across_figure_captions_and_pages() -> None:
    from app.core.ir import InlineRun, RawBlock
    from app.core.structure_infer import build_ir

    root = build_ir([
        RawBlock(
            text="Remarque :\n1) Ne superposez pas.\n2) Alignez les caisses.",
            page=1,
        ),
        RawBlock(text="Figure 5.1 Empilage correct\nFigure 5.2 Empilage incorrect", page=1),
        RawBlock(
            text="3) \x07Soutenez les pieds.",
            page=2,
            inline_runs=[
                InlineRun("3) "),
                InlineRun("\x07"),
                InlineRun("Soutenez les pieds.", italic=True),
            ],
        ),
        RawBlock(text="Figure 5.3 Appui correct\nFigure 5.4 Appui incorrect", page=2),
        RawBlock(text="4) Ajoutez des lattes.", page=2),
        RawBlock(text="Figure 5.5 Lattes supplémentaires", page=2),
        RawBlock(text="5.3 Paliers", page=2, heading_level=1),
    ])

    note = next(node for node in root.walk() if node.kind == "admonition")
    sequence = note.children[0]

    assert note.text == "Remarque :"
    assert sequence.kind == "item-sequence" and sequence.form == "ordered"
    assert [item.text for item in sequence.children] == [
        "Ne superposez pas.",
        "Alignez les caisses.",
        "Soutenez les pieds.",
        "Ajoutez des lattes.",
    ]
    assert sequence.children[2].inline_runs == [
        InlineRun("Soutenez les pieds.", italic=True),
    ]


def test_numbered_note_items_can_follow_a_separate_note_label() -> None:
    from app.core.ir import RawBlock
    from app.core.structure_infer import build_ir

    root = build_ir([
        RawBlock(text="Remarque :", page=1),
        RawBlock(text="Figure 1 Empilage correct", page=1),
        RawBlock(text="1) Alignez les caisses.", page=1),
        RawBlock(text="2) Soutenez les pieds.", page=1),
        RawBlock(text="Fin de la note.", page=1),
    ])

    note = next(node for node in root.walk() if node.kind == "admonition")
    assert [item.text for item in note.children[0].children] == [
        "Alignez les caisses.",
        "Soutenez les pieds.",
    ]


def test_inline_numbered_and_lettered_lists_split_into_nested_items() -> None:
    from app.core.ir import RawBlock
    from app.core.structure_infer import build_ir

    root = build_ir([RawBlock(
        text=(
            "Vérifiez les éléments :\n"
            "1. Résistance d’isolation, voir l’article 5.4.\n"
            "2. Paliers :\n"
            "a. Paliers à roulement avec détail\ncontinué sur la ligne suivante.\n"
            "b. Palier lisse.\n"
            "3. Conditions de fonctionnement.\n"
            "4. Boîte à bornes :\n"
            "a. L’intérieur est propre.\n"
            "b. Les contacts sont raccordés.\n"
            "c. Les entrées sont hermétiques.\n"
            "5. Refroidissement."
        ),
        page=1,
    )])

    sequences = [node for node in root.walk() if node.kind == "item-sequence"]
    numbered = next(sequence for sequence in sequences if sequence.form == "ordered")

    assert len(numbered.children) == 5
    assert "5.4" in numbered.children[0].text
    first_sublist = numbered.children[1].children[0]
    second_sublist = numbered.children[3].children[0]
    assert first_sublist.form == second_sublist.form == "lettered"
    assert [item.text for item in first_sublist.children] == [
        "a. Paliers à roulement avec détail\ncontinué sur la ligne suivante.",
        "b. Palier lisse.",
    ]
    assert [item.text for item in second_sublist.children] == [
        "a. L’intérieur est propre.",
        "b. Les contacts sont raccordés.",
        "c. Les entrées sont hermétiques.",
    ]


def test_lettered_list_blocks_nest_under_number_and_resume_numbering() -> None:
    from app.core.ir import RawBlock
    from app.core.structure_infer import build_ir

    root = build_ir([
        RawBlock(text="1. Résistance d’isolation.", page=1),
        RawBlock(text="2. Paliers :", page=1),
        RawBlock(text="a. Paliers à roulement.", page=1),
        RawBlock(text="b. Palier lisse.", page=1),
        RawBlock(text="3. Refroidissement.", page=1),
    ])
    numbered = next(node for node in root.walk() if node.kind == "item-sequence")

    assert numbered.form == "ordered"
    assert [item.text for item in numbered.children] == [
        "Résistance d’isolation.",
        "Paliers :",
        "Refroidissement.",
    ]
    assert [item.text for item in numbered.children[1].children[0].children] == [
        "a. Paliers à roulement.",
        "b. Palier lisse.",
    ]
