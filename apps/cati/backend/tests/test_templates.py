"""Tests routes /api/v1/templates + resolution a l'export."""

from __future__ import annotations

import io

import openpyxl


def _upload_tpl(client, xlsx: bytes, name: str = "Mon template"):
    return client.post(
        "/api/v1/templates",
        files=[("file", ("template.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
        data={"name": name, "sheet_name": "Catalogue"},
    )


def _upload_pdf(client, pdf_bytes: bytes) -> str:
    resp = client.post("/api/v1/documents", files=[("files", ("plan.pdf", pdf_bytes, "application/pdf"))])
    return resp.json()["results"][0]["document_id"]


def test_list_empty(client) -> None:
    assert client.get("/api/v1/templates").json() == []


def test_upload_first_becomes_default(client, template_xlsx_bytes) -> None:
    resp = _upload_tpl(client, template_xlsx_bytes)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_default"] is True
    assert body["name"] == "Mon template"
    assert "module" in body["header_columns"]


def test_upload_rejects_wrong_sheet(client) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "AutreFeuille"
    buf = io.BytesIO()
    wb.save(buf)
    resp = _upload_tpl(client, buf.getvalue())
    assert resp.status_code == 400
    assert resp.json()["code"] == "TEMPLATE_SHEET_MISSING"


def test_set_default_and_delete(client, template_xlsx_bytes) -> None:
    a = _upload_tpl(client, template_xlsx_bytes, "A").json()
    b = _upload_tpl(client, template_xlsx_bytes, "B").json()
    assert a["is_default"] is True
    assert b["is_default"] is False

    # Bascule le defaut sur B.
    nb = client.post(f"/api/v1/templates/{b['id']}/default").json()
    assert nb["is_default"] is True
    defaults = [t for t in client.get("/api/v1/templates").json() if t["is_default"]]
    assert len(defaults) == 1 and defaults[0]["id"] == b["id"]

    # Supprime le defaut B -> A redevient defaut.
    client.delete(f"/api/v1/templates/{b['id']}")
    remaining = client.get("/api/v1/templates").json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == a["id"]
    assert remaining[0]["is_default"] is True


def test_export_uses_uploaded_template(client, cati_pdf_bytes, template_xlsx_bytes) -> None:
    _upload_tpl(client, template_xlsx_bytes)
    doc_id = _upload_pdf(client, cati_pdf_bytes)

    resp = client.get(f"/api/v1/documents/{doc_id}/export.xlsx")
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb["Catalogue"]
    figs = [ws.cell(r, 3).value for r in range(1, ws.max_row + 1)]
    assert "10A" in figs and "20A" in figs
