"""Tests DMRL : chargement, bornes de DM, PMC, decoupage IR.

Fixtures 100 % synthetiques (regle CLAUDE.md : jamais de donnee utilisateur).
"""

from __future__ import annotations

import json

import pytest
from lxml import etree

from app.core import splitter
from app.core.dmrl import (
    DmrlEntry,
    entry_from_dict,
    extract_icn_filenames,
    find_dm_boundaries,
    generate_pmc,
    load_dmrl,
)
from app.core.errors import AppError
from app.core.ir import IRNode
from app.core.pmc import parse_dmc

_ROWS = [
    {"Arbo": "1", "DMC": "DMC-BRAKE-A-00-00-00-00A-040A-D", "Titre": "Description generale",
     "Type": "Descriptif"},
    {"Arbo": "1.1", "DMC": "DMC-BRAKE-A-00-00-00-00A-520A-D", "Titre": "Depose du frein",
     "Type": "Procedure"},
    {"Arbo": "2", "DMC": "DMC-BRAKE-A-00-00-00-00A-941A-D", "Titre": "Catalogue de pieces",
     "Type": ""},
]


@pytest.fixture
def dmrl_json(tmp_path):
    path = tmp_path / "DMRL.json"
    path.write_text(json.dumps(_ROWS), encoding="utf-8")
    return path


def test_load_dmrl_json_maps_columns(dmrl_json):
    entries = load_dmrl(dmrl_json)
    assert [e.title for e in entries] == ["Description generale", "Depose du frein",
                                          "Catalogue de pieces"]
    assert entries[0].dm_type == "descriptive"
    assert entries[1].dm_type == "procedural"
    # Type absent -> deduit de l'info code du DMC (941 = IPD).
    assert entries[2].dm_type == "ipd"
    assert entries[1].arbo == "1.1"


def test_load_dmrl_prefers_explicit_type_de_dm_over_dmc(tmp_path):
    path = tmp_path / "dmrl.json"
    path.write_text(json.dumps([
        {"DMC": "DMC-BRAKE-A-00-00-00-00A-040A-D", "Titre": "Procedure", "Type de DM": "PROCED"},
        {"DMC": "DMC-BRAKE-A-00-00-00-00A-520A-D", "Titre": "Description", "Type de DM": "DESCR"},
        {"DMC": "DMC-BRAKE-A-00-00-00-00A-941A-D", "Titre": "Parts", "Type de DM": "IPD"},
    ]), encoding="utf-8")

    assert [entry.dm_type for entry in load_dmrl(path)] == [
        "procedural", "descriptive", "ipd"
    ]


def test_load_dmrl_csv_accents_and_semicolon(tmp_path):
    path = tmp_path / "dmrl.csv"
    path.write_text(
        "Arbo;Code DM;Titre;Nature\n1;DMC-X-A-00-00-00-00A-040A-D;Présentation;Descriptif\n",
        encoding="utf-8",
    )
    entries = load_dmrl(path)
    assert entries[0].title == "Présentation"
    assert entries[0].dm_type == "descriptive"


def test_load_dmrl_splits_ssc_into_subsystem_components(tmp_path):
    path = tmp_path / "dmrl.json"
    path.write_text(
        json.dumps([{
            "MIC": "BRAKE",
            "SDC": "A",
            "SC": "00",
            "SSC": "12",
            "AC": "00",
            "DC": "00",
            "DCV": "A",
            "IC": "040",
            "ICV": "A",
            "ILC": "D",
            "Titre": "Description",
        }]),
        encoding="utf-8",
    )

    entry = load_dmrl(path)[0]

    assert entry.sub_system_code == "1"
    assert entry.sub_sub_system_code == "2"


def test_load_dmrl_maps_node_title_and_client_code_columns(tmp_path):
    path = tmp_path / "dmrl.json"
    path.write_text(json.dumps([{
        "Titre Nœud": "Dépose de la roue",
        "Techname": "Roue",
        "Infoname": "Dépose",
        "SDC": "A",
        "System": "01",
        "Ssystem": "2",
        "SSSystem": "3",
        "Assy": "04",
        "Discode": "05",
        "DiscodeV": "B",
        "Infocode": "520",
    }]), encoding="utf-8")

    entry = load_dmrl(path)[0]

    assert entry.title == "Dépose de la roue"
    assert entry.tech_name == "Roue"
    assert entry.info_name == "Dépose"
    assert entry.system_diff_code == "A"
    assert entry.system_code == "01"
    assert entry.sub_system_code == "2"
    assert entry.sub_sub_system_code == "3"
    assert entry.assy_code == "04"
    assert entry.disassy_code == "05"
    assert entry.disassy_code_variant == "B"
    assert entry.info_code == "520"


def test_load_dmrl_reads_multiple_icns_and_round_trips_them(tmp_path):
    path = tmp_path / "dmrl.json"
    icn_cell = "ICN-WEG-AA0004-00001-A-02.jpg\r\nICN-WEG-AA0004-00002-A-02.png"
    path.write_text(json.dumps([{"Titre": "Description", "ICN": icn_cell}]), encoding="utf-8")

    entry = load_dmrl(path)[0]

    assert extract_icn_filenames(entry.icn) == [
        "ICN-WEG-AA0004-00001-A-02.jpg",
        "ICN-WEG-AA0004-00002-A-02.png",
    ]
    assert entry_from_dict(entry.to_dict()).icn == icn_cell


def test_load_dmrl_rejects_unknown_format(tmp_path):
    path = tmp_path / "dmrl.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(AppError):
        load_dmrl(path)


def test_load_dmrl_rejects_empty(tmp_path):
    path = tmp_path / "dmrl.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(AppError):
        load_dmrl(path)


def test_find_dm_boundaries_contiguous_and_missing(dmrl_json):
    entries = load_dmrl(dmrl_json)
    text = (
        "Manuel de maintenance\n"
        "Description generale\n"
        "Le frein est compose de deux etriers.\n"
        "Depose du frein\n"
        "Deposer les vis puis retirer l'etrier.\n"
    )
    bounds = find_dm_boundaries(text, entries)
    matched = [b for b in bounds if b["matched"]]
    assert [b["title"] for b in matched] == ["Description generale", "Depose du frein"]
    # Les bornes s'enchainent sans trou et couvrent la fin du document.
    assert matched[0]["end"] == matched[1]["start"]
    assert matched[1]["end"] == len(text)
    assert text[matched[0]["start"]:matched[0]["end"]].startswith("Description generale")
    # L'entree non trouvee reste presente (jamais supprimee en silence).
    missing = [b for b in bounds if not b["matched"]]
    assert [b["title"] for b in missing] == ["Catalogue de pieces"]


def test_find_dm_boundaries_ignores_accents_and_case(tmp_path):
    entries = [DmrlEntry(title="Depose du frein")]
    bounds = find_dm_boundaries("blabla\nDÉPOSE DU FREIN\ncontenu", entries)
    assert bounds[0]["matched"] is True


def test_parse_dmc_components():
    parsed = parse_dmc("DMC-BRAKE-A-00-00-00-00A-040A-D")
    assert parsed is not None
    assert parsed["modelIdentCode"] == "BRAKE"
    assert parsed["infoCode"] == "040"
    assert parsed["itemLocationCode"] == "D"
    assert parse_dmc("pas-un-dmc") is None


def test_parse_dmc_accepts_two_character_system_difference_code():
    parsed = parse_dmc("DMC-WEG-AA-00-09-00-00A-040A-A")

    assert parsed is not None
    assert parsed["modelIdentCode"] == "WEG"
    assert parsed["systemDiffCode"] == "AA"
    assert parsed["systemCode"] == "00"
    assert parsed["subSystemCode"] == "0"
    assert parsed["subSubSystemCode"] == "9"
    assert parsed["assyCode"] == "00"


def test_generate_pmc_hierarchy(dmrl_json):
    xml = generate_pmc(load_dmrl(dmrl_json), pm_title="Frein")
    root = etree.fromstring(xml.encode("utf-8"))
    top = root.findall("./content/pmEntry")
    assert len(top) == 2                                   # Arbo "1" et "2"
    assert top[0].findtext("pmEntryTitle") == "Description generale"
    nested = top[0].findall("./pmEntry")                   # Arbo "1.1" imbrique
    assert len(nested) == 1
    assert nested[0].findtext("pmEntryTitle") == "Depose du frein"
    assert root.find(".//dmCode").get("modelIdentCode") == "BRAKE"
    assert root.findtext("./identAndStatusSection/pmAddress/pmTitle") == "Frein"


def test_generate_pmc_numeric_arbo_builds_outline_and_resets():
    entries = [
        DmrlEntry(arbo="1", dmc="DMC-BRAKE-A-00-00-00-00A-040A-D", title="Terminologie"),
        DmrlEntry(arbo="1", dmc="DMC-BRAKE-A-00-00-00-00A-520A-D", title="Recommandations"),
        DmrlEntry(arbo="2", dmc="DMC-BRAKE-A-00-00-00-00A-012A-D", title="Pictogramme"),
        DmrlEntry(arbo="2", dmc="DMC-BRAKE-A-00-00-00-00A-720A-D", title="Reception"),
        DmrlEntry(arbo="3", dmc="DMC-BRAKE-A-00-00-00-00A-721A-D", title="Detail reception"),
        DmrlEntry(arbo="1", dmc="DMC-BRAKE-A-00-00-00-00A-130A-D", title="Securite"),
        DmrlEntry(arbo="1", dmc="DMC-BRAKE-A-00-00-00-00A-041A-D", title="Manutention"),
        DmrlEntry(arbo="2", dmc="DMC-BRAKE-A-00-00-00-00A-042A-D", title="Levage"),
        DmrlEntry(arbo="3", dmc="DMC-BRAKE-A-00-00-00-00A-043A-D", title="Moteur horizontal"),
        DmrlEntry(arbo="1", dmc="DMC-BRAKE-A-00-00-00-00A-044A-D", title="Stockage"),
    ]

    root = etree.fromstring(generate_pmc(entries).encode("utf-8"))
    top = root.findall("./content/pmEntry")

    assert [entry.findtext("pmEntryTitle") for entry in top] == [
        "Terminologie", "Recommandations", "Securite", "Manutention", "Stockage"
    ]
    recommendations = top[1].findall("./pmEntry")
    assert [entry.findtext("pmEntryTitle") for entry in recommendations] == [
        "Pictogramme", "Reception"
    ]
    assert recommendations[1].findtext("./pmEntry/pmEntryTitle") == "Detail reception"
    handling = top[3].find("./pmEntry")
    assert handling.findtext("pmEntryTitle") == "Levage"
    assert handling.findtext("./pmEntry/pmEntryTitle") == "Moteur horizontal"
    assert len(root.findall(".//dmRef")) == len(entries)
    assert [ref.findtext("./dmRefAddressItems/dmTitle/techName") for ref in root.findall(".//dmRef")] == [
        entry.title for entry in entries
    ]


def _ir_with_sections() -> IRNode:
    def sec(title: str, body: str) -> IRNode:
        return IRNode(id=title, kind="section", level=1, text=title, children=[
            IRNode(id=f"{title}-p", kind="paragraph", text=body),
        ])

    return IRNode(id="root", kind="section", level=0, children=[
        sec("Description generale", "Le frein comporte deux etriers."),
        sec("Depose du frein", "Deposer les vis."),
    ])


def test_split_by_dmrl_uses_dmrl_titles():
    entries = [
        DmrlEntry(dmc="DMC-BRAKE-A-00-00-00-00A-520A-D", title="Depose du frein"),
        DmrlEntry(dmc="DMC-BRAKE-A-00-00-00-00A-040A-D", title="Description generale"),
    ]
    units = splitter.split_by_dmrl(_ir_with_sections(), entries)
    titles = [u.title for u in units]
    assert set(titles) == {"Description generale", "Depose du frein"}
    assert {u.title: u.dmc for u in units} == {
        "Description generale": "DMC-BRAKE-A-00-00-00-00A-040A-D",
        "Depose du frein": "DMC-BRAKE-A-00-00-00-00A-520A-D",
    }
    contents = {u.title: splitter.ir_to_text(u.root) for u in units}
    assert "Le frein comporte deux etriers." in contents["Description generale"]
    assert "Deposer les vis." in contents["Depose du frein"]
    assert units[0].root.children[0].text == "Description generale"
    assert units[1].root.children[0].text == "Depose du frein"


def test_split_by_dmrl_prefers_section_title_over_body_contains():
    root = IRNode(id="root", kind="section", level=0, children=[
        IRNode(
            id="transport",
            kind="section",
            level=1,
            text="4. MANUTENTION ET TRANSPORT",
            children=[
                IRNode(
                    id="transport-p",
                    kind="paragraph",
                    text="Utilisez des appareils de levage adaptes.",
                ),
                IRNode(
                    id="lifting",
                    kind="section",
                    level=2,
                    text="4.1. LEVAGE",
                    children=[IRNode(id="lifting-p", kind="paragraph", text="Soulevez le moteur.")],
                ),
            ],
        ),
    ])
    entries = [
        DmrlEntry(title="Manutention et transport"),
        DmrlEntry(title="Levage"),
    ]

    units = splitter.split_by_dmrl(root, entries)
    contents = {unit.title: splitter.ir_to_text(unit.root) for unit in units}

    assert "Utilisez des appareils de levage adaptes." in contents["Manutention et transport"]
    assert "Utilisez des appareils de levage adaptes." not in contents["Levage"]
    assert "Soulevez le moteur." in contents["Levage"]


def test_split_by_dmrl_excludes_layout_noise_zones():
    root = IRNode(id="root", kind="section", level=0, children=[
        IRNode(id="header", kind="paragraph", text="www.example.test", zone="header"),
        IRNode(id="toc", kind="paragraph", text="FRANCAIS", zone="toc"),
        IRNode(id="cover", kind="paragraph", text="Manual", zone="cover"),
        IRNode(id="footer", kind="paragraph", text="Page 1", zone="footer"),
        IRNode(
            id="terminologie",
            kind="section",
            level=1,
            text="1. TERMINOLOGIE",
            children=[IRNode(id="body", kind="paragraph", text="Definitions.")],
        ),
    ])

    units = splitter.split_by_dmrl(root, [DmrlEntry(title="Terminologie")])

    assert len(units) == 1
    assert units[0].is_orphan is False
    assert splitter.ir_to_text(units[0].root) == "1. TERMINOLOGIE\nDefinitions."


def test_split_by_dmrl_ignores_running_header_before_first_dm():
    root = IRNode(id="root", kind="section", level=0, children=[
        IRNode(id="header", kind="paragraph", text="www.weg.net", zone="header"),
        IRNode(
            id="terminologie",
            kind="section",
            level=1,
            text="1. TERMINOLOGIE",
            children=[IRNode(id="body", kind="paragraph", text="Definitions.")],
        ),
    ])

    units = splitter.split_by_dmrl(root, [DmrlEntry(title="Terminologie")])

    assert len(units) == 1
    assert units[0].is_orphan is False
    assert splitter.ir_to_text(units[0].root) == "1. TERMINOLOGIE\nDefinitions."


def test_split_by_dmrl_keeps_missing_entry_as_empty_dm():
    entries = [DmrlEntry(title="Description generale"), DmrlEntry(title="Chapitre absent")]
    units = splitter.split_by_dmrl(_ir_with_sections(), entries)
    assert [u.title for u in units][-1] == "Chapitre absent"
    assert units[-1].root.children == []
