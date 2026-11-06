"""Norm of a document: detection endpoint, per-run choice, S1000D without page revision tracking."""

from __future__ import annotations

import json
from typing import Any

import fitz
import pytest
from fastapi.testclient import TestClient

from app.api import analyze as analyze_api

_COVER = "Manufacturer Code: F9111\nProduct\nC13088 SERIES\nIssue No: 005\n2026-01-29\n22-15-10\nPage TP-1"
_CONFIGURATION = (
    "Configuration\nF9111FCTN-A-22-15-10-00A-020A-D\n1. Product configuration\nTable\n"
    "PN class\nPN\nMFR\nPRIME\nC13088AA03\nF9111\nALT\n109-0770V04-2A02\nAGUSTA\n"
    "PRIME\nC13088AA04\nF9111\n2. Publication configuration\nTable\nPRIME\n22-15-10\nF9111"
)
_LOEDM = (
    "LIST OF EFFECTIVE DATA MODULES\nF9111FCTN-A-22-15-10-00A-020A-D\n002\n2026-01-29\nC\n"
)
_HIGHLIGHTS = (
    "HIGHLIGHTS\nThe listed changes are introduced in issue 005.\nData module/Technical publication\n"
    "Reason for update\nPage number\nF9111FCTN-A-22-15-10-00A-020A-D\n"
    "Migration ATA 2200 en S1000D 4.2\nCONF-1"
)


def _pdf(*texts: str) -> bytes:
    pdf = fitz.open()
    for text in texts:
        page = pdf.new_page()
        page.insert_textbox(fitz.Rect(30, 30, 560, 800), text, fontname="helv", fontsize=11)
    data = pdf.tobytes()
    pdf.close()
    return data


def _upload(client: TestClient, data: bytes) -> str:
    response = client.post(
        "/api/v1/documents", files={"file": ("manual.pdf", data, "application/pdf")}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _s1000d_pdf(*, highlights: str = _HIGHLIGHTS) -> bytes:
    return _pdf(_COVER, _CONFIGURATION, _LOEDM, highlights)


def _set_context(client: TestClient, document_id: str) -> None:
    response = client.patch(
        f"/api/v1/documents/{document_id}",
        json={
            "meta_revision_date": "JAN 29/26",
            "meta_cmm_number": "22-15-10",
            "meta_first_issue_date": "JAN 2006",
            "meta_revision_number": "005",
            "meta_pnr_number": "C13088AA03",
            "document_language": "en",
        },
    )
    assert response.status_code == 200, response.text


def _events(body: bytes) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []
    for block in body.decode("utf-8").replace("\r\n", "\n").split("\n\n"):
        name, data = "", ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
        if name:
            events.append((name, json.loads(data) if data.startswith(("{", "[")) else data))
    return events


def test_norm_endpoint_detects_s1000d_and_the_default_norm(client: TestClient) -> None:
    s1000d = client.get(f"/api/v1/documents/{_upload(client, _s1000d_pdf())}/norm")
    assert s1000d.status_code == 200, s1000d.text
    body = s1000d.json()
    assert body["detected_norm"] == "s1000d"
    assert body["default_norm"] == "ata100"
    assert body["page_revision_tracking"] is False
    assert {item["code"]: item["label"] for item in body["norms"]} == {
        "ata100": "ATA100",
        "s1000d": "S1000D",
    }

    classic = client.get(f"/api/v1/documents/{_upload(client, _pdf('HIGHLIGHTS', 'Page 2'))}/norm")
    assert classic.json()["detected_norm"] == "ata100"
    assert classic.json()["page_revision_tracking"] is True


def test_norm_endpoint_unknown_document(client: TestClient) -> None:
    response = client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000/norm")
    assert response.status_code == 404


def test_metadata_suggestions_follow_the_s1000d_front_matter(client: TestClient) -> None:
    document_id = _upload(client, _s1000d_pdf())

    response = client.post(f"/api/v1/documents/{document_id}/metadata-suggestions")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "pages_scanned": 4,
        "meta_cmm_number": "22-15-10",
        "meta_pnr_number": ["C13088AA03", "C13088AA04"],
        "meta_revision_number": "005",
        "meta_revision_date": "JAN 29/26",
        "meta_first_issue_date": None,
        "meta_update_type": "Migration",
    }


def test_update_type_is_mco_when_a_reason_is_not_a_migration(client: TestClient) -> None:
    highlights = _HIGHLIGHTS + (
        "\nF9111FCTN-A-22-15-10-00A-340A-A\nEnvironmental conditions updated\nTEST-3"
    )
    document_id = _upload(client, _s1000d_pdf(highlights=highlights))

    response = client.post(f"/api/v1/documents/{document_id}/metadata-suggestions")

    assert response.json()["meta_update_type"] == "MCO"


def test_analyze_rejects_an_unknown_norm(client: TestClient) -> None:
    document_id = _upload(client, _s1000d_pdf())
    _set_context(client, document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze?norm=iso9001")

    assert response.status_code == 422
    assert response.json()["code"] == "NORM_INVALID"


def test_s1000d_analysis_does_not_track_modified_pages(client: TestClient) -> None:
    document_id = _upload(client, _s1000d_pdf())
    _set_context(client, document_id)

    with client.stream("POST", f"/api/v1/documents/{document_id}/analyze") as stream:
        assert stream.status_code == 200
        events = _events(b"".join(stream.iter_bytes()))

    statuses = next(data for name, data in events if name == "page_statuses")
    assert statuses == {"pages": []}
    assert events[-1][0] == "done"


def test_chosen_norm_ata100_keeps_page_revision_tracking(client: TestClient) -> None:
    document_id = _upload(client, _s1000d_pdf())
    _set_context(client, document_id)

    with client.stream("POST", f"/api/v1/documents/{document_id}/analyze?norm=ata100") as stream:
        assert stream.status_code == 200
        events = _events(b"".join(stream.iter_bytes()))

    statuses = next(data for name, data in events if name == "page_statuses")
    assert len(statuses["pages"]) == 4
    warnings = [message for name, data in events if name == "warning" for message in data["messages"]]
    assert any("Norme choisie pour cette analyse : ATA100" in message for message in warnings)


def test_chapter_parity_is_a_cmm_convention_not_an_s1000d_one(client: TestClient) -> None:
    # No HIGHLIGHTS page: under ATA100 every page stays in the analysis scope.
    pdf = _pdf(_COVER, "Chapter 1 General\n" + _CONFIGURATION, _LOEDM)

    def parity_findings(query: str) -> int:
        document_id = _upload(client, pdf)
        _set_context(client, document_id)
        with client.stream("POST", f"/api/v1/documents/{document_id}/analyze{query}") as stream:
            b"".join(stream.iter_bytes())
        rows = client.get(f"/api/v1/documents/{document_id}/suggestions").json()
        return sum(1 for row in rows if row["rule_code"] == "LAYOUT_CHAPTER_PARITY")

    assert parity_findings("") == 0
    assert parity_findings("?norm=ata100") > 0


@pytest.mark.parametrize("norm", ["auto", "AUTO", ""])
def test_auto_norm_is_the_detected_one(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, norm: str
) -> None:
    document_id = _upload(client, _s1000d_pdf())
    _set_context(client, document_id)
    captured: dict[str, Any] = {}

    def capture(*_args: Any, **kwargs: Any) -> list[Any]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(analyze_api, "run_all", capture)
    with client.stream("POST", f"/api/v1/documents/{document_id}/analyze?norm={norm}") as stream:
        b"".join(stream.iter_bytes())

    assert captured["norm"] is None
    assert captured["filter_norms"] is True
