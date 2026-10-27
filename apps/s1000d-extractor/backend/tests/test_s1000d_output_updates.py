"""Regression tests for S1000D identifiers, PMC codes, and output formatting."""

import json

import pytest
from lxml import etree

from app.core import xml_safe
from app.core.dmrl import DmrlEntry
from app.core.errors import AppError
from app.core.ir import IRNode
from app.core.pmc import generate_pmc
from app.core.s1000d_schema import validate_xsd
from app.core.s1000d_serializer import serialize


def _parse_dm(xml: str) -> etree._Element:
    return xml_safe.fromstring(xml, allow_internal_dtd=True)


def test_procedural_preliminary_data_and_all_content_ids_are_complete() -> None:
    root = IRNode(id="root", kind="section", level=0, children=[
        IRNode(
            id="tools",
            kind="section",
            text="Tools Required",
            children=[IRNode(
                id="tool-list",
                kind="item-sequence",
                form="bullet",
                children=[
                    IRNode(id="tool-1", kind="item", text="Special wrench"),
                    IRNode(id="tool-2", kind="item", text="Tire lever"),
                ],
            )],
        ),
        IRNode(
            id="supplies",
            kind="section",
            text="Supplies",
            children=[IRNode(
                id="supply-list",
                kind="item-sequence",
                form="bullet",
                children=[IRNode(id="supply-1", kind="item", text="Lubricant")],
            )],
        ),
        IRNode(
            id="spares",
            kind="section",
            text="Spare Parts",
            children=[IRNode(
                id="spare-list",
                kind="item-sequence",
                form="bullet",
                children=[IRNode(id="spare-1", kind="item", text="Tire")],
            )],
        ),
        IRNode(
            id="step-1",
            kind="section",
            text="1. Remove the wheel",
            children=[
                IRNode(
                    id="figure-1",
                    kind="figure",
                    text="Figure 1 — Wheel position ICN-WEG-AA0004-00001-A-02.png",
                    icn="ICN-WEG-AA0004-00001-A-02.png",
                ),
                IRNode(
                    id="table-1",
                    kind="table",
                    text="Table 1 — Tightening values",
                    table_rows=[["Bolt", "Torque"], ["M6", "12"]],
                ),
            ],
        ),
        IRNode(
            id="step-2",
            kind="section",
            text="2. Install the wheel",
            children=[IRNode(
                id="action",
                kind="paragraph",
                text="Install the wheel.",
            )],
        ),
    ])

    xml = serialize(root, issue="4.2", dm_type="procedural")
    document = _parse_dm(xml)
    preliminary = document.find("./content/procedure/preliminaryRqmts")
    assert preliminary is not None
    assert preliminary.find("./productionMaintData") is None
    assert [
        step.get("id")
        for step in document.findall("./content/procedure/mainProcedure/proceduralStep")
    ] == ["stp-0001", "stp-0002"]
    assert [figure.get("id") for figure in document.findall(".//figure")] == ["fig-0001"]
    assert [table.get("id") for table in document.findall(".//table")] == ["tab-0001"]
    assert [
        item.get("id")
        for item in document.findall(".//supportEquipDescr")
    ] == ["seq-0001", "seq-0002"]
    assert [item.get("id") for item in document.findall(".//supplyDescr")] == ["sup-0001"]
    assert [item.get("id") for item in document.findall(".//spareDescr")] == ["spa-0001"]

    figure_title = document.findtext(".//figure/title") or ""
    assert "ICN-" not in figure_title
    assert document.find(".//figure/graphic").get(
        "infoEntityIdent"
    ) == "ICN-WEG-AA0004-00001-A-02"
    assert "\n  <identAndStatusSection>" in xml
    assert "\n        <reqCondGroup>" in xml
    errors = [
        violation for violation in validate_xsd(
            xml, "4.2", dm_type="procedural", allow_internal_dtd=True
        )
        if violation["severity"] == "error"
    ]
    assert errors == []


def test_pmc_emits_decomposed_dm_code_from_component_fields() -> None:
    entry = DmrlEntry(
        dmc="client-code",
        title="Wheel installation",
        model_ident_code="WEG",
        system_diff_code="AA",
        system_code="00",
        sub_system_code="0",
        sub_sub_system_code="9",
        assy_code="00",
        disassy_code="00",
        disassy_code_variant="A",
        info_code="040",
        info_code_variant="A",
        item_location_code="A",
    )

    xml = generate_pmc([entry])
    dm_code = etree.fromstring(xml.encode("utf-8")).find(".//dmCode")

    assert dm_code is not None
    assert dm_code.attrib == {
        "modelIdentCode": "WEG",
        "systemDiffCode": "AA",
        "systemCode": "00",
        "subSystemCode": "0",
        "subSubSystemCode": "9",
        "assyCode": "00",
        "disassyCode": "00",
        "disassyCodeVariant": "A",
        "infoCode": "040",
        "infoCodeVariant": "A",
        "itemLocationCode": "A",
    }
    assert "dmCodeValue" not in xml


def test_pmc_rejects_an_unparseable_dm_code() -> None:
    with pytest.raises(AppError) as exc_info:
        generate_pmc([DmrlEntry(dmc="not-a-dmc", title="Invalid entry")])

    assert exc_info.value.code == "PMC_INVALID_DMC"
    assert exc_info.value.status_code == 422


def test_pmc_download_uses_source_name_and_decomposes_component_dmc(client, pdf_bytes) -> None:
    document = client.post(
        "/api/v1/documents",
        files={"file": ("Manual de test.pdf", pdf_bytes)},
        data={"s1000d_issue": "4.2", "context_hint": "mixed"},
    )
    assert document.status_code == 201, document.text
    doc_id = document.json()["id"]
    dmrl = [{
        "Arbo": "1",
        "DMC": "DMC-TESTMODEL-B72-ENG-10-00-0000-ABCA-A_123-45",
        "Title": "Synthetic engineering",
        "MIC": "TESTMODEL",
        "SDC": "B72",
        "SC": "ENG",
        "SSC": "10",
        "AC": "00",
        "DC": "00",
        "DCV": "00",
        "IC": "ABC",
        "ICV": "A",
        "ILC": "A",
    }]
    uploaded = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("dmrl.json", json.dumps(dmrl).encode("utf-8"))},
    )
    assert uploaded.status_code == 200, uploaded.text

    pmc = client.get(f"/api/v1/documents/{doc_id}/pmc")

    assert pmc.status_code == 200, pmc.text
    assert pmc.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''PMC-Manual%20de%20test.xml"
    )
    dm_code = etree.fromstring(pmc.content).find(".//dmCode")
    assert dm_code is not None
    assert dm_code.get("modelIdentCode") == "TESTMODEL"
    assert dm_code.get("systemDiffCode") == "B72"
    assert dm_code.get("systemCode") == "ENG"
    assert dm_code.get("subSystemCode") == "1"
    assert dm_code.get("subSubSystemCode") == "0"
    assert dm_code.get("disassyCodeVariant") == "00"
    assert dm_code.get("infoCode") == "ABC"
    assert dm_code.get("itemLocationCode") == "A"
    assert "dmCodeValue" not in pmc.text
