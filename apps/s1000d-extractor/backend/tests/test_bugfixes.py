"""Non-regressions des deux bugs bloquants.

Bug 1 : "Unexpected Server Error" a la generation/validation.
Bug 2 : duplication des illustrations.
"""

from __future__ import annotations

from lxml import etree

from app.core.ir import IRNode
from app.core.s1000d_serializer import serialize
from app.core.validator import validate_document
from app.core.wizard import images_dir


def _upload(client, data: bytes, name: str = "manual.pdf") -> str:
    r = client.post(
        "/api/v1/documents",
        files={"file": (name, data)},
        data={"s1000d_issue": "5.0", "context_hint": "mixed"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


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
    xml = serialize(root, issue="5.0", dm_type="descriptive", title="Titre\x0c")
    etree.fromstring(xml.encode("utf-8"))
    assert "\x0c" not in xml and "\x00" not in xml


def test_serialize_admonition_without_candidates() -> None:
    """Une admonition non resolue (candidats vides) levait une IndexError."""
    root = IRNode(id="r", kind="section", level=0, children=[
        IRNode(id="n1", kind="admonition", admonition="warning", text="Danger."),
    ])
    xml = serialize(root, issue="5.0", dm_type="descriptive")
    assert "<warning>" in xml


def test_serialize_rejects_invalid_element_name() -> None:
    """Un override humain fantaisiste ne doit pas faire planter la serialisation."""
    node = IRNode(id="n1", kind="paragraph", text="x")
    node.candidates = [type("C", (), {"element": "1 mauvais nom", "score": 1.0,
                                      "rationale": ""})()]
    xml = serialize(IRNode(id="r", kind="section", level=0, children=[node]),
                    issue="5.0", dm_type="descriptive")
    etree.fromstring(xml.encode("utf-8"))


def test_validate_document_never_raises_on_bad_brex() -> None:
    xml = serialize(IRNode(id="r", kind="section", level=0), issue="5.0", dm_type="descriptive")
    violations = validate_document(xml, issue="5.0", brex_xml="<pas-un-brex")
    assert isinstance(violations, list)
    assert any(v["rule"] in ("BREX", "XSD") for v in violations)


def test_wizard_generate_returns_200_on_hostile_document(client, pdf_bytes) -> None:
    state = _run_wizard(client, _upload(client, pdf_bytes))
    assert state["step"] == "generate"
    assert all(d["has_xml"] for d in state["dms"])


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
