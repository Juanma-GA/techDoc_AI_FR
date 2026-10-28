"""Editable rule settings use only isolated synthetic configuration/documents."""

import hashlib
import json

import pytest
from sqlalchemy import delete

from app.core import preliminary_review
from app.core.ir import IRNode, to_dict
from app.core.preliminary_detection import passages, suggestion
from app.core.preliminary_rule_defaults import default_entries
from app.core.preliminary_rules import CONFIG_KEY, RuleGroup, RulesConfig, RulesUpdate, read_rules, write_rules
from app.core.procedure_semantics import heading_label, normalize
from app.db.models import AppConfig, Document
from app.db.session import SessionLocal

URL = "/api/v1/settings/preliminary-rules"


@pytest.fixture(autouse=True)
def clean_rules():
    with SessionLocal() as db:
        db.execute(delete(AppConfig).where(AppConfig.key == CONFIG_KEY))
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(delete(AppConfig).where(AppConfig.key == CONFIG_KEY))
        db.commit()


def rule(fr="verrou de transport", en="transport lock", category="support", kind="keyword"):
    return {"category": category, "kind": kind,
            "fr": fr if isinstance(fr, list) else [fr], "en": en if isinstance(en, list) else [en]}


def save(client, rules, revision=0):
    return client.post(
        URL, json={"revision": revision, "groups": rules},
        headers={"X-Request-Id": "synthetic-rules-request"},
    )


def test_defaults_are_bilingual_editable_and_do_not_create_configuration_on_read(client):
    response = client.get(URL)
    assert response.status_code == 200
    payload = response.json()
    assert payload["revision"] == 0
    assert len(payload["groups"]) == 12
    assert {r["category"] for r in payload["groups"]} == {
        "conditions", "personnel", "support", "supplies", "spares", "safety",
    }
    assert all(r["fr"] and r["en"] for r in payload["groups"])
    legacy = default_entries()
    for group in payload["groups"]:
        normalizer = heading_label if group["kind"] == "heading" else normalize
        for language in ("fr", "en"):
            expected = {
                normalizer(entry[language]) for entry in legacy
                if entry["category"] == group["category"] and entry["kind"] == group["kind"]
            }
            assert {normalizer(value) for value in group[language]} == expected
            assert len(group[language]) == len(expected)
    assert client.post(URL, json=payload).status_code == 200
    with SessionLocal() as db:
        assert db.get(AppConfig, CONFIG_KEY) is None
        old_payload = {"revision": 0, "rules": [
            {key: entry[key] for key in ("category", "kind", "fr", "en")} for entry in legacy
        ]}
        old_json = json.dumps(old_payload, ensure_ascii=False, separators=(",", ":"))
        assert read_rules(db).fingerprint == hashlib.sha256(old_json.encode()).hexdigest()


def test_add_edit_delete_and_empty_configuration_persist_in_new_sessions(client):
    first = save(client, [rule()])
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1
    with SessionLocal() as db:
        assert read_rules(db).groups[0].en == ["transport lock"]
        assert json.loads(db.get(AppConfig, CONFIG_KEY).value) == first.json()
    assert save(client, [rule()], 1).json()["revision"] == 1  # No-op does not stale reviews.
    edited = save(client, [rule("adaptateur", "adapter", "spares")], 1)
    assert edited.json()["revision"] == 2
    assert client.get(URL).json() == edited.json()
    assert save(client, [], 2).json() == {"revision": 3, "groups": []}
    with SessionLocal() as db:
        assert read_rules(db).groups == []  # Empty is intentional, never a fallback to defaults.


@pytest.mark.parametrize("changes", [
    {"fr": []}, {"en": []}, {"fr": ["   "]}, {"en": [" \t "]}, {"en": None},
    {"fr": ["a\nb"]}, {"en": ["x" * 201]}, {"category": "closing"}, {"kind": "regex"},
    {"fr": "not a list"},
    {"unexpected": True},
])
def test_invalid_or_incomplete_bilingual_entries_are_rejected(client, changes):
    response = save(client, [{**rule(), **changes}])
    assert response.status_code == 422, response.text
    assert client.get(URL).json()["revision"] == 0


@pytest.mark.parametrize("missing", ["fr", "en"])
def test_both_languages_are_required(client, missing):
    entry = rule()
    del entry[missing]
    assert save(client, [entry]).status_code == 422


def test_duplicates_conflicting_categories_and_reserved_structure_are_explicit_errors(client):
    for entries, code in [
        ([rule(), rule()], "RULES_DUPLICATE"),
        ([rule(fr=["Étau", "etau"])], "RULES_DUPLICATE"),
        ([rule(), rule(category="safety")], "RULES_CATEGORY_CONFLICT"),
        ([rule("Procédure principale", "Main procedure", kind="heading")], "RULES_RESERVED_HEADING"),
        ([rule("Clôture", "Closing requirements", kind="heading")], "RULES_RESERVED_HEADING"),
    ]:
        response = save(client, entries)
        assert response.status_code == 422, response.text
        assert response.json()["code"] == code
        assert response.json()["request_id"]


def test_stale_settings_tabs_do_not_overwrite_new_rules(client):
    assert save(client, [rule()]).status_code == 200
    response = save(client, [rule("autre", "other")])
    assert response.status_code == 409
    assert response.json()["code"] == "RULES_CONFLICT"
    assert client.get(URL).json()["groups"] == [rule()]


def test_bilingual_literals_accents_boundaries_and_no_regular_expression_execution(client):
    assert save(client, [rule("Étau spécial", "Special vise"), rule("a+b", "x.*y", "supplies")]).status_code == 200
    with SessionLocal() as db:
        config = read_rules(db)
    for text in ("ÉTAU spécial disponible.", "Special vise available."):
        assert suggestion(text, None, rules=config) == ("support", "keywords")
    assert suggestion("special vises", None, rules=config) == ("body", "unmatched")
    assert suggestion("xAAAAy", None, rules=config) == ("body", "unmatched")
    assert suggestion("Use the special vise.", None, rules=config) == ("body", "action")
    assert suggestion("x.*y", None, rules=config) == ("supplies", "keywords")
    assert suggestion("Tool", None, rules=config) == ("body", "unmatched")  # Defaults were replaced.
    assert suggestion("Special vise and a+b.", None, rules=config) == ("review", "multiple")
    assert suggestion("Special vise", None, phase="main", rules=config) == ("body", "main")
    assert suggestion("Special vise", None, phase="closing", rules=config) == ("closing", "closing")
    assert suggestion("Special vise", None, admonition="warning", rules=config) == ("safety", "admonition")


@pytest.mark.parametrize("heading", ["4.2 Équipements de banc", "4.2 Bench resources"])
@pytest.mark.parametrize("numbering", ["", "7.4 "])
def test_custom_headings_and_table_columns_supply_context_without_classifying_the_heading(heading, numbering):
    config = RulesConfig(revision=1, groups=[RuleGroup(**rule(
        numbering + "Équipements de banc", numbering + "Bench resources", kind="heading",
    ))])
    tree = to_dict(IRNode(id="root", kind="section", children=[
        IRNode(id="h", kind="section", text=heading, children=[
            IRNode(id="p", kind="paragraph", text="Fixture ABC."),
        ]),
        IRNode(id="t", kind="table", table_rows=[["Bench resources", "Qty"], ["Fixture XYZ", "1"]]),
    ]))
    items = passages(tree, source_format="docx", page_offset=0, rules=config)
    assert [p["suggested"] for p in items] == ["body", "support", "body", "support"]
    assert items[0]["role"] == "heading"
    assert items[2]["role"] == "table-header"
    assert all(p["decision"] is None for p in items)


@pytest.fixture
def procedure(client, tmp_path):
    tree = IRNode(id="root", kind="section", children=[
        IRNode(id="resources", kind="section", text="Bench resources", children=[
            IRNode(id="fixture", kind="paragraph", text="Fixture ABC."),
        ]),
        IRNode(id="lock", kind="paragraph", text="Transport lock available."),
        IRNode(id="action", kind="paragraph", text="Disconnect the connector."),
    ])
    with SessionLocal() as db:
        doc = Document(
            filename="synthetic.docx", source_format="docx", storage_path=str(tmp_path / "synthetic.docx"),
            s1000d_issue="4.2", wizard_step="preliminary", status="wizard",
            dms_json=json.dumps([{
                "dm_id": "proc", "dm_type": "procedural", "title": "Synthetic removal", "tree": to_dict(tree),
            }]),
        )
        db.add(doc)
        db.flush()
        preliminary_review.prepare(doc)
        db.commit()
        return doc.id


def action(client, doc_id, **params):
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]
    return client.post(
        f"/api/v1/documents/{doc_id}/wizard/preliminary",
        json={"revision": state["revision"], "dm_id": "proc", **params},
    )


def test_rule_changes_stale_saved_decisions_until_explicit_restart_and_split_uses_new_rules(client, procedure):
    doc_id = procedure
    assert action(client, doc_id, op="decide", passage_id="lock:text:0", destination="support").status_code == 200
    with SessionLocal() as db:
        before = db.get(Document, doc_id).preliminary_review_json
    assert save(client, [rule()]).status_code == 200
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]
    assert state["reviews"]["proc"]["status"] == "stale"
    assert state["reviews"]["proc"]["passages"][2]["decision"] == "support"
    with SessionLocal() as db:
        assert db.get(Document, doc_id).preliminary_review_json == before
    assert action(client, doc_id, op="complete", confirm_empty=True).status_code == 409
    assert client.get(f"/api/v1/documents/{doc_id}/wizard/dm/proc/xml").status_code == 409
    assert client.get(f"/api/v1/documents/{doc_id}/wizard/zip").status_code == 409
    restarted = action(client, doc_id, op="restart")
    assert restarted.status_code == 200
    review = restarted.json()["reviews"]["proc"]
    assert review["rules_revision"] == 1
    assert review["passages"][2]["suggested"] == "support"
    assert all(p["decision"] is None for p in review["passages"])
    split = action(client, doc_id, op="split", passage_id="lock:text:0", split_at=14)
    assert split.status_code == 200, split.text
    fragments = split.json()["reviews"]["proc"]["passages"][2:4]
    assert [p["suggested"] for p in fragments] == ["support", "body"]


def test_custom_headings_project_from_saved_context_and_do_not_become_steps(client, procedure):
    from app.core.ir import from_dict
    from app.core.preliminary_projection import reviewed_root

    assert save(client, [rule("Équipements de banc", "Bench resources", kind="heading")]).status_code == 200
    state = action(client, procedure, op="restart").json()
    for passage in state["reviews"]["proc"]["passages"]:
        if passage.get("role") != "content":
            continue
        response = action(client, procedure, op="decide", passage_id=passage["id"],
                          destination=passage["suggested"])
        assert response.status_code == 200
    assert action(client, procedure, op="complete", confirm_empty=True).status_code == 200
    with SessionLocal() as db:
        doc = db.get(Document, procedure)
        dm = json.loads(doc.dms_json)[0]
        result = reviewed_root(doc, dm, from_dict(dm["tree"]))
        assert "Bench resources" not in [node.text for node in result.walk()]
        assert result.reviewed_requirements["support"][0].children[0].text == "Fixture ABC."
        original = doc.preliminary_review_json
    assert save(client, [], 1).status_code == 200
    with SessionLocal() as db:
        doc = db.get(Document, procedure)
        doc.wizard_step = "generate"
        db.commit()
    resumed = client.get(f"/api/v1/documents/{procedure}/wizard")
    assert resumed.json()["step"] == "preliminary"
    assert resumed.json()["preliminary"]["reviews"]["proc"]["status"] == "stale"
    with SessionLocal() as db:
        assert db.get(Document, procedure).preliminary_review_json == original


def test_document_reset_preserves_rule_settings(client):
    saved = save(client, [rule()]).json()
    response = client.post("/api/v1/admin/reset/all", params={"confirm_token": "synthetic-confirmation"})
    assert response.status_code == 200
    assert client.get(URL).json() == saved


def test_corrupt_persisted_settings_fail_explicitly_instead_of_using_defaults(client):
    with SessionLocal() as db:
        db.add(AppConfig(key=CONFIG_KEY, value="not valid JSON"))
        db.commit()
    response = client.get(URL)
    assert response.status_code == 500
    assert response.json()["code"] == "RULES_STORAGE_INVALID"


def test_settings_changed_during_review_save_are_caught_by_document_compare_and_swap(
    client, procedure, monkeypatch,
):
    with SessionLocal() as db:
        before = db.get(Document, procedure).preliminary_review_json
        revision = preliminary_review.load(db.get(Document, procedure))["revision"]

    def change_after_read(db):
        snapshot = read_rules(db)
        with SessionLocal() as other:
            write_rules(other, RulesUpdate(revision=0, groups=[RuleGroup(**rule())]))
        return snapshot

    monkeypatch.setattr(preliminary_review, "read_rules", change_after_read)
    response = client.post(
        f"/api/v1/documents/{procedure}/wizard/preliminary",
        json={"revision": revision, "dm_id": "proc", "op": "decide",
              "passage_id": "lock:text:0", "destination": "support"},
    )
    assert response.status_code == 409, response.text
    with SessionLocal() as db:
        assert db.get(Document, procedure).preliminary_review_json == before


def test_custom_table_heading_keeps_resource_name_quantity_and_reference(client, tmp_path):
    from app.core.preliminary_projection import reviewed_root
    from app.core.procedure_semantics import resource_rows

    assert save(client, [rule("Équipements de banc", "Bench resources", kind="heading")]).status_code == 200
    tree = IRNode(id="root", kind="section", children=[
        IRNode(id="table", kind="table", table_rows=[
            ["Bench resources", "Qty", "Part number"], ["Fixture ABC", "2", "FIX-001"],
        ]),
        IRNode(id="action", kind="paragraph", text="Disconnect the connector."),
    ])
    with SessionLocal() as db:
        doc = Document(
            filename="synthetic.docx", source_format="docx", storage_path=str(tmp_path / "synthetic.docx"),
            s1000d_issue="4.2", wizard_step="preliminary", status="wizard",
            dms_json=json.dumps([{
                "dm_id": "proc", "dm_type": "procedural", "title": "Synthetic removal", "tree": to_dict(tree),
            }]),
        )
        db.add(doc)
        db.flush()
        preliminary_review.prepare(doc)
        state = preliminary_review.load(doc)
        for passage in state["reviews"]["proc"]["passages"]:
            if passage.get("role") == "content":
                passage["decision"] = passage["suggested"]
        state["reviews"]["proc"]["status"] = "reviewed"
        doc.preliminary_review_json = json.dumps(state)
        projected = reviewed_root(doc, json.loads(doc.dms_json)[0], tree)
        resources = resource_rows(projected.reviewed_requirements["support"])
        assert [(r.name, r.quantity, r.part_number) for r in resources] == [("Fixture ABC", "2", "FIX-001")]
        assert tree.children[0].table_rows[0][0] == "Bench resources"


def test_independent_language_lists_allow_different_lengths_and_noop_group_ordering(client):
    groups = [
        rule(fr=["verrou", "étau"], en=["fixture"], category="support"),
        rule(fr=["hors tension"], en=["power isolated", "supply isolated"], category="conditions"),
    ]
    response = save(client, groups)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 1
    assert save(client, list(reversed(groups)), 1).json()["revision"] == 1
    with SessionLocal() as db:
        config = read_rules(db)
    for text in ("ÉTAU disponible", "Fixture available", "Verrou disponible"):
        assert suggestion(text, None, rules=config) == ("support", "keywords")


@pytest.mark.parametrize("entries", [
    [],
    [
        {"category": "support", "kind": "keyword", "fr": "étau", "en": "vise"},
        {"category": "support", "kind": "keyword", "fr": "étau", "en": "fixture"},
        {"category": "support", "kind": "heading", "fr": "Équipements de banc", "en": "Bench resources"},
    ],
])
def test_existing_paired_json_is_read_losslessly_without_writing_or_incrementing_revision(client, entries):
    value = json.dumps({"revision": 7, "rules": entries})
    with SessionLocal() as db:
        db.add(AppConfig(key=CONFIG_KEY, value=value))
        db.commit()
    response = client.get(URL)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 7
    assert "rules" not in response.json()
    if entries:
        assert response.json()["groups"][0] == rule(fr=["étau"], en=["vise", "fixture"])
        with SessionLocal() as db:
            config = read_rules(db)
        assert suggestion("Fixture", None, rules=config) == ("support", "keywords")
        assert suggestion("Vise", None, rules=config) == ("support", "keywords")
        assert config.headings["support"] == {"equipements de banc", "bench resources"}
    else:
        assert response.json()["groups"] == []
    assert client.post(URL, json=response.json()).json()["revision"] == 7
    with SessionLocal() as db:
        assert db.get(AppConfig, CONFIG_KEY).value == value
        old_json = json.dumps({"revision": 7, "rules": entries}, ensure_ascii=False, separators=(",", ":"))
        assert read_rules(db).fingerprint == hashlib.sha256(old_json.encode()).hexdigest()
    changed = save(client, [rule(fr=["étau", "support"], en=["vise"])], 7)
    assert changed.status_code == 200
    with SessionLocal() as db:
        assert "groups" in json.loads(db.get(AppConfig, CONFIG_KEY).value)


@pytest.mark.parametrize("language", ["fr", "en"])
def test_language_expression_limit_is_enforced_across_groups(client, language):
    groups = [rule(category="conditions"), rule(fr="étau", en="vise")]
    for index, group in enumerate(groups):
        group[language] = [f"synthetic {index} term {number}" for number in range(500)]
    response = save(client, groups)
    assert response.status_code == 200, response.text
    groups[0][language].append("extra expression")
    response = save(client, groups, 1)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "RULES_TOO_MANY"
    assert client.get(URL).json()["revision"] == 1
