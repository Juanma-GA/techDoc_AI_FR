"""Tests des listes a puces, des templates de DM et des regles client BREX."""

from __future__ import annotations

import json

import pytest
from lxml import etree

from app.core import dm_templates
from app.core.brex_rules import load_brex_rules, validate_dm_against_brex
from app.core.errors import AppError
from app.core.lists import parse_lists, to_s1000d

# --- listes a puces ---------------------------------------------------------


def test_parse_lists_bullet():
    assert parse_lists("- Item A\n- Item B") == "<ul><li>Item A</li><li>Item B</li></ul>"


def test_parse_lists_ordered_and_prose():
    out = parse_lists("Intro du paragraphe.\n1. Deposer\n2. Reposer")
    assert out == "<p>Intro du paragraphe.</p><ol><li>Deposer</li><li>Reposer</li></ol>"


def test_parse_lists_nested_by_indentation():
    out = parse_lists("- Niveau 1\n  - Niveau 2\n- Retour niveau 1")
    assert out == (
        "<ul><li>Niveau 1</li><ul><li>Niveau 2</li></ul><li>Retour niveau 1</li></ul>"
    )


def test_parse_lists_escapes_and_is_well_formed():
    out = parse_lists("- Serrer <A> & <B>")
    assert "&amp;" in out and "&lt;A&gt;" in out
    etree.fromstring(f"<root>{out}</root>".encode())


def test_parse_lists_switches_kind_at_same_level():
    out = parse_lists("- Puce\n1. Numero")
    assert out == "<ul><li>Puce</li></ul><ol><li>Numero</li></ol>"


def test_to_s1000d_vocabulary():
    xml = to_s1000d(parse_lists("- Item A\n1. Etape"))
    assert xml == (
        "<randomList><listItem><para>Item A</para></listItem></randomList>"
        "<sequentialList><listItem><para>Etape</para></listItem></sequentialList>"
    )


# --- templates --------------------------------------------------------------

_TEMPLATE = {
    "name": "descriptive",
    "dm_type": "descriptive",
    "sections": [
        {"key": "introduction", "title": "Introduction", "required": False,
         "match": ["introduction"]},
        {"key": "description", "title": "Description", "required": True,
         "match": ["description"]},
    ],
    "defaults": {"security": {"securityClassification": "01"}, "originator": "TODO"},
}


def test_load_templates_reads_dir(tmp_path):
    (tmp_path / "t1.json").write_text(json.dumps(_TEMPLATE), encoding="utf-8")
    templates = dm_templates.load_templates(tmp_path)
    assert "descriptive" in templates
    assert dm_templates.template_for(templates, "descriptive")["name"] == "descriptive"


def test_load_templates_rejects_invalid_json(tmp_path):
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    with pytest.raises(AppError):
        dm_templates.load_templates(tmp_path)


def test_load_templates_missing_dir_is_empty(tmp_path):
    assert dm_templates.load_templates(tmp_path / "absent") == {}


def test_shipped_templates_cover_the_three_dm_types():
    templates = dm_templates.load_templates()
    types = {t.get("dm_type") for t in templates.values()}
    assert {"descriptive", "procedural", "ipd"} <= types


def test_apply_template_merges_defaults_without_losing_dm_values():
    dm = {"dm_id": "dm1", "title": "Frein", "dm_type": "descriptive",
          "meta": {"security": {"securityClassification": "02"}}}
    out = dm_templates.apply_template(dm, _TEMPLATE)
    # Fusion PROFONDE : la valeur du DM gagne, les autres defauts sont conserves.
    assert out["meta"]["security"]["securityClassification"] == "02"
    assert out["meta"]["originator"] == "TODO"
    assert [s["key"] for s in out["sections"]] == ["introduction", "description"]
    assert out["missing_fields"] == ["description"]
    assert "sections" not in dm            # le DM d'entree n'est pas mute


def test_generate_dm_dispatches_content_and_converts_lists():
    dm = {"dm_id": "dm1", "title": "Frein", "dm_type": "descriptive"}
    text = (
        "Introduction\n"
        "Ce module decrit le frein.\n"
        "Description\n"
        "- etrier\n"
        "- disque\n"
    )
    out = dm_templates.generate_dm(dm, _TEMPLATE, text)
    sections = {s["key"]: s for s in out["sections"]}
    assert sections["introduction"]["content"] == "Ce module decrit le frein."
    assert sections["description"]["html"] == "<ul><li>etrier</li><li>disque</li></ul>"
    assert out["missing_fields"] == []
    etree.fromstring(f"<root>{out['content_xml']}</root>".encode())


def test_generate_dm_routes_unheaded_body_to_required_description():
    dm = {"dm_id": "dm1", "title": "Frein", "dm_type": "descriptive"}
    text = "Le frein ralentit la roue.\nIl est actionne par le circuit hydraulique."

    out = dm_templates.generate_dm(dm, _TEMPLATE, text)
    sections = {section["key"]: section for section in out["sections"]}

    assert sections["introduction"]["content"] == ""
    assert sections["description"]["content"] == text
    assert out["missing_fields"] == []


def test_generate_dm_matches_numbered_section_headings():
    dm = {"dm_id": "dm1", "title": "Frein", "dm_type": "descriptive"}
    text = "1. Introduction\nVue generale.\n2. Description\nFonctionnement du frein."

    out = dm_templates.generate_dm(dm, _TEMPLATE, text)
    sections = {section["key"]: section for section in out["sections"]}

    assert sections["introduction"]["content"] == "Vue generale."
    assert sections["description"]["content"] == "Fonctionnement du frein."
    assert out["missing_fields"] == []


def test_procedural_dm_without_preliminary_requirements_has_no_warning():
    template = dm_templates.load_templates()["procedural"]
    dm = {"dm_id": "dm1", "title": "Frein", "dm_type": "procedural"}

    out = dm_templates.generate_dm(dm, template, "Déposer le capot.")
    sections = {section["key"]: section for section in out["sections"]}

    assert sections["preliminary"]["content"] == ""
    assert sections["procedure"]["content"] == "Déposer le capot."
    assert out["missing_fields"] == []


def test_procedural_dm_keeps_preliminary_requirements_when_present():
    template = dm_templates.load_templates()["procedural"]
    dm = {"dm_id": "dm1", "title": "Frein", "dm_type": "procedural"}
    text = (
        "Conditions préalables\nIsoler l'alimentation.\n"
        "Procédure\nDéposer le capot."
    )

    out = dm_templates.generate_dm(dm, template, text)
    sections = {section["key"]: section for section in out["sections"]}

    assert sections["preliminary"]["content"] == "Isoler l'alimentation."
    assert sections["procedure"]["content"] == "Déposer le capot."
    assert out["missing_fields"] == []


def test_generate_dm_slices_on_dmrl_boundaries():
    text = "AVANT\nIntroduction\nContenu du DM.\nAPRES"
    dm = {"dm_id": "dm1", "title": "T", "dm_type": "descriptive",
          "start": text.index("Introduction"), "end": text.index("APRES")}
    out = dm_templates.generate_dm(dm, _TEMPLATE, text)
    joined = " ".join(s["content"] for s in out["sections"])
    assert "Contenu du DM." in joined
    assert "AVANT" not in joined and "APRES" not in joined


# --- regles client (BREX JSON) ----------------------------------------------

_RULES = {
    "name": "Client X",
    "max_title_levels": 2,
    "max_title_length": 20,
    "allowed_dm_types": ["descriptive"],
    "forbidden_kinds": ["table"],
    "required_sections": ["description"],
    "max_list_depth": 1,
}


def _node(kind: str, **kw) -> dict:
    return {"id": kw.pop("id", kind), "kind": kind, "text": kw.pop("text", ""),
            "children": kw.pop("children", []), **kw}


def test_load_brex_rules_flags_unknown_keys(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"max_title_levels": 2, "lubie": 1}), encoding="utf-8")
    rules = load_brex_rules(path)
    assert rules["_unknown_keys"] == ["lubie"]


def test_load_brex_rules_rejects_invalid(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(AppError):
        load_brex_rules(path)


def test_validate_dm_against_brex_detects_all_violations():
    tree = _node("section", id="root", children=[
        _node("section", id="s1", text="Niveau 1", children=[
            _node("section", id="s2", text="Niveau 2", children=[
                _node("section", id="s3", text="Niveau 3 interdit"),
            ]),
        ]),
        _node("table", id="t1"),
        _node("item-sequence", id="l1", children=[
            _node("item-sequence", id="l2", children=[_node("item", id="i1")]),
        ]),
    ])
    dm = {"dm_id": "dm1", "title": "Un titre beaucoup trop long pour le client",
          "dm_type": "procedural", "tree": tree, "sections": []}
    rules = {r["rule"] for r in validate_dm_against_brex(dm, _RULES)}
    assert rules == {
        "BREX_DM_TYPE", "BREX_TITLE_LEVEL", "BREX_TITLE_LENGTH",
        "BREX_FORBIDDEN", "BREX_REQUIRED_SECTION", "BREX_LIST_DEPTH",
    }


def test_validate_dm_against_brex_clean_dm():
    tree = _node("section", id="root", children=[_node("section", id="s1", text="Court")])
    dm = {"dm_id": "dm1", "title": "Court", "dm_type": "descriptive", "tree": tree,
          "sections": [{"key": "description", "content": "du contenu"}]}
    assert validate_dm_against_brex(dm, _RULES) == []


def test_validate_dm_against_brex_no_rules_is_noop():
    assert validate_dm_against_brex({"tree": {}}, {}) == []
