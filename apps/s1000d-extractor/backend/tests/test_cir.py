"""Tests CIR : chargement du repository et resolution des references."""

from __future__ import annotations

import pytest

from app.core.cir import load_cir, resolve_cir_references
from app.core.errors import AppError

_CIR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<commonRepository>
  <warning id="WARN-001"><warningAndCautionPara>Couper l'alimentation.</warningAndCautionPara></warning>
  <caution id="CAUT-002"><warningAndCautionPara>Ne pas forcer.</warningAndCautionPara></caution>
  <toolRef id="TOOL-01"><name>Cle dynamometrique</name></toolRef>
</commonRepository>
"""


@pytest.fixture
def cir_file(tmp_path):
    path = tmp_path / "cir.xml"
    path.write_text(_CIR_XML, encoding="utf-8")
    return path


def test_load_cir_indexes_entries_by_id(cir_file):
    cir = load_cir(cir_file)
    assert set(cir) == {"WARN-001", "CAUT-002", "TOOL-01"}
    assert cir["WARN-001"]["type"] == "warning"
    assert cir["WARN-001"]["text"] == "Couper l'alimentation."
    assert cir["TOOL-01"]["type"] == "tool"


def test_load_cir_rejects_malformed(tmp_path):
    path = tmp_path / "cir.xml"
    path.write_text("<a><b></a>", encoding="utf-8")
    with pytest.raises(AppError):
        load_cir(path)


def test_load_cir_rejects_missing(tmp_path):
    with pytest.raises(AppError):
        load_cir(tmp_path / "absent.xml")


def test_load_cir_blocks_external_entities(tmp_path):
    """XXE : les entites externes ne doivent jamais etre resolues (le contenu du
    CIR finit dans les DM generes et dans l'UI)."""
    secret = tmp_path / "secret.txt"
    secret.write_text("MOT-DE-PASSE", encoding="utf-8")
    path = tmp_path / "cir.xml"
    path.write_text(
        '<?xml version="1.0"?>'
        f'<!DOCTYPE r [<!ENTITY xxe SYSTEM "file:///{secret.as_posix()}">]>'
        '<commonRepository><warning id="W1">&xxe;</warning></commonRepository>',
        encoding="utf-8",
    )
    with pytest.raises(AppError) as exc:
        load_cir(path)
    assert "MOT-DE-PASSE" not in str(exc.value)


def test_load_cir_blocks_entity_expansion_bomb(tmp_path):
    path = tmp_path / "cir.xml"
    path.write_text(
        '<?xml version="1.0"?>'
        '<!DOCTYPE r [<!ENTITY a "aaaaaaaaaa">'
        '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
        '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>'
        '<commonRepository><warning id="W1">&c;</warning></commonRepository>',
        encoding="utf-8",
    )
    with pytest.raises(AppError):
        load_cir(path)


def test_resolve_cir_references_all_syntaxes(cir_file):
    cir = load_cir(cir_file)
    dm = {
        "dm_id": "dm1",
        "title": "Depose {{CIR:TOOL-01}}",
        "tree": {
            "id": "root", "kind": "section", "text": "", "children": [
                {"id": "n1", "kind": "admonition", "text": "{{CIR:WARN-001}}", "children": []},
                {"id": "n2", "kind": "paragraph", "text": "[CIR:CAUT-002]", "children": []},
                {"id": "n3", "kind": "paragraph",
                 "text": 'Outil <cirRef refId="TOOL-01"/>', "children": []},
            ],
        },
        "sections": [{"key": "procedure", "content": "Avant : {{CIR:WARN-001}}"}],
    }
    out = resolve_cir_references(dm, cir)
    kids = out["tree"]["children"]
    assert kids[0]["text"] == "Couper l'alimentation."
    assert kids[1]["text"] == "Ne pas forcer."
    assert kids[2]["text"] == "Outil Cle dynamometrique"
    assert out["title"] == "Depose Cle dynamometrique"
    assert out["sections"][0]["content"] == "Avant : Couper l'alimentation."
    assert out["cir_used"] == ["CAUT-002", "TOOL-01", "WARN-001"]
    assert out["cir_unresolved"] == []
    assert dm["tree"]["children"][0]["text"] == "{{CIR:WARN-001}}"  # entree non mutee


def test_resolve_cir_references_keeps_unknown_reference(cir_file):
    cir = load_cir(cir_file)
    dm = {"title": "", "tree": {"id": "n1", "kind": "paragraph",
                                "text": "{{CIR:INCONNU}}", "children": []}}
    out = resolve_cir_references(dm, cir)
    # Jamais d'effacement silencieux : la reference reste et remonte en anomalie.
    assert out["tree"]["text"] == "{{CIR:INCONNU}}"
    assert out["cir_unresolved"] == ["INCONNU"]


def test_resolve_cir_references_without_cir_is_noop():
    dm = {"title": "T", "tree": {"id": "n1", "kind": "paragraph", "text": "x", "children": []}}
    assert resolve_cir_references(dm, {}) == dm
