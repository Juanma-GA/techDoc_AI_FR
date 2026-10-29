from __future__ import annotations

import json
from types import SimpleNamespace

from app.core import wizard
from app.core.ir import Candidate, IRNode, to_dict
from app.core import preliminary_review
from app.db.models import Document


def test_wizard_guides_and_persists_a_brex_compliant_candidate(monkeypatch) -> None:
    brex_xml = (
        "<dmodule><content><brex><contextRules><structureObjectRuleGroup>"
        '<structureObjectRule id="no-nested-step">'
        '<objectPath allowedObjectFlag="0">'
        "//proceduralStep/proceduralStep"
        "</objectPath></structureObjectRule>"
        "</structureObjectRuleGroup></contextRules></brex></content></dmodule>"
    )
    paragraph = IRNode(
        id="paragraph",
        kind="paragraph",
        text="Disconnect the connector.",
        context="procedural",
        candidates=[
            Candidate("proceduralStep", 0.6, "Nested step"),
            Candidate("para", 0.4, "Paragraph"),
        ],
    )
    root = IRNode(
        id="root",
        kind="section",
        children=[
            IRNode(
                id="step",
                kind="section",
                text="Removal",
                context="procedural",
                candidates=[Candidate("proceduralStep", 0.8, "Procedure step")],
                children=[paragraph],
            )
        ],
    )
    document = Document(
        id="doc-1",
        filename="synthetic.docx", source_format="docx", storage_path="synthetic-unused",
        s1000d_issue="4.2",
        brex_id="brex-1",
        dmrl_json=None,
        dms_json=json.dumps([{
            "dm_id": "dm-1",
            "dmc": "",
            "title": "Removal",
            "dm_type": "procedural",
            "tree": to_dict(root),
        }]),
    )
    preliminary_review.prepare(document)
    review_state = preliminary_review.load(document)
    for procedure in review_state["reviews"].values():
        for passage in procedure["passages"]:
            passage["decision"] = "body"
        procedure["status"] = "reviewed"
    document.preliminary_review_json = json.dumps(review_state)

    monkeypatch.setattr(wizard, "_brex_xml", lambda *_args: brex_xml)
    monkeypatch.setattr(wizard, "extract_brex_dm_code", lambda _xml: None)
    monkeypatch.setattr(
        wizard.wres,
        "load_resources",
        lambda _doc: SimpleNamespace(header_template=None, brex_rules=None),
    )
    monkeypatch.setattr(wizard.wres, "dmrl_entries", lambda _doc: [])
    monkeypatch.setattr(wizard.wres, "dmrl_data_module_entries", lambda _doc: [])
    monkeypatch.setattr(wizard.wres, "apply_resources", lambda dm, _res: (dm, []))

    wizard._generate_all(None, document)

    generated_dm = json.loads(document.dms_json)[0]
    generated_root = generated_dm["tree"]
    generated_paragraph = generated_root["children"][0]["children"][0]
    assert generated_paragraph["candidates"][0]["element"] == "para"
    assert "choix guidé par le BREX" in generated_paragraph["candidates"][0]["rationale"]
    assert not [
        violation for violation in generated_dm["violations"]
        if violation.get("rule") in {"BREX", "BREX_VALUE"}
        and violation.get("severity") == "error"
    ]
