"""Routes /api/v1/parse/* et /api/v1/render/* (sans persistance)."""

from __future__ import annotations

import io
from xml.etree import ElementTree as ET

from openpyxl import load_workbook


def _graph(client, sample_dsl: str) -> dict:
    res = client.post("/api/v1/parse/json", json={"content": sample_dsl})
    assert res.status_code == 200, res.text
    return res.json()["graph"]


def test_formats(client) -> None:
    formats = {f["format"] for f in client.get("/api/v1/formats").json()}
    assert {"mermaid", "svg", "drawio", "bpmn", "pptx", "xlsx", "json", "s1000d"} <= formats


def test_parse_dsl_keeps_details(client, sample_dsl) -> None:
    graph = _graph(client, sample_dsl)
    c1 = next(n for n in graph["nodes"] if n["id"] == "C1")
    assert c1["type"] == "check"
    assert c1["expected"] == "13,8 a 14,5 V"
    assert c1["tools"] == "multimetre"


def test_parse_json_invalid(client) -> None:
    res = client.post("/api/v1/parse/json", json={"content": '{"nodes": "oops"}'})
    assert res.status_code == 422
    assert res.json()["code"] == "FLOW_INVALID"


def test_parse_text_llm_disabled_fallback(client) -> None:
    client.post("/api/v1/settings", json={"llm_enabled": False})
    text = (
        "Le moteur ne demarre pas\nCouper le contact\n"
        "Verifier la batterie (attendu: 12 V)\nRemplacer la batterie\nFin"
    )
    res = client.post("/api/v1/parse/text", json={"text": text})
    assert res.status_code == 200
    body = res.json()
    assert body["llm_used"] is False
    types = [n["type"] for n in body["graph"]["nodes"]]
    assert types[0] == "start" and "safety" in types and "repair" in types


def test_parse_table_roundtrip(client, sample_dsl) -> None:
    graph = _graph(client, sample_dsl)
    xlsx = client.post("/api/v1/render/xlsx", json=graph).content
    res = client.post("/api/v1/parse/table", files={"file": ("flow.xlsx", xlsx)})
    assert res.status_code == 200, res.text
    nodes = {n["id"]: n for n in res.json()["graph"]["nodes"]}
    assert nodes["C1"]["expected"] == "13,8 a 14,5 V"
    assert nodes["SEC"]["warning"]


def test_parse_table_rejects_bad_type(client) -> None:
    res = client.post("/api/v1/parse/table", files={"file": ("flow.txt", b"x")})
    assert res.status_code == 415


def test_render_preview_svg(client, sample_dsl) -> None:
    res = client.post("/api/v1/render/preview", json=_graph(client, sample_dsl))
    assert res.status_code == 200
    assert ET.fromstring(res.content).tag.endswith("svg")


def test_render_all_formats(client, sample_dsl) -> None:
    graph = _graph(client, sample_dsl)
    for fmt in ("mermaid", "svg", "drawio", "bpmn", "pptx", "xlsx", "json", "s1000d"):
        res = client.post(f"/api/v1/render/{fmt}", json=graph)
        assert res.status_code == 200, fmt
        assert "attachment" in res.headers["content-disposition"]


def test_render_unknown_format(client, sample_dsl) -> None:
    res = client.post("/api/v1/render/vsdx", json=_graph(client, sample_dsl))
    assert res.status_code == 404
    assert res.json()["code"] == "FORMAT_UNKNOWN"


def test_mermaid_no_bare_end_class(client, sample_dsl) -> None:
    text = client.post("/api/v1/render/mermaid", json=_graph(client, sample_dsl)).text
    assert ":::end\n" not in text and not text.rstrip().endswith(":::end")


def test_s1000d_structure(client, sample_dsl) -> None:
    xml = client.post("/api/v1/render/s1000d", json=_graph(client, sample_dsl)).content
    root = ET.fromstring(xml)
    assert root.tag == "dmodule"
    assert root.find(".//faultIsolationProcedure") is not None
    assert root.find(".//fault").get("faultCode") == "P0562"
    assert root.findall(".//isolationStep")
    assert root.find(".//yesNoAnswer") is not None


def test_xlsx_has_steps_sheet(client, sample_dsl) -> None:
    content = client.post("/api/v1/render/xlsx", json=_graph(client, sample_dsl)).content
    wb = load_workbook(io.BytesIO(content))
    assert any("tape" in name for name in wb.sheetnames)
