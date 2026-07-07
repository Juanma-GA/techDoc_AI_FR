"""Test route /api/v1/documents/{id}/export.xlsx."""

from __future__ import annotations

import io

import openpyxl


def _upload(client, pdf_bytes: bytes) -> str:
    resp = client.post(
        "/api/v1/documents",
        files=[("files", ("plan.pdf", pdf_bytes, "application/pdf"))],
    )
    return resp.json()["results"][0]["document_id"]


def test_export_xlsx_roundtrip(client, cati_pdf_bytes) -> None:
    doc_id = _upload(client, cati_pdf_bytes)
    client.put(
        f"/api/v1/documents/{doc_id}/header-meta",
        json={"module": "F1-PL", "otan_supplier": "NOM FRN"},
    )

    resp = client.get(f"/api/v1/documents/{doc_id}/export.xlsx")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]

    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    assert "Catalogue" in wb.sheetnames
    ws = wb["Catalogue"]
    assert ws.cell(1, 1).value == "module"  # en-tete preserve
    # 2 articles ecrits (module fourni -> bloc en-tete 1 ligne puis articles).
    figs = [ws.cell(r, 3).value for r in range(2, ws.max_row + 1)]
    assert "10A" in figs and "20A" in figs


def test_export_excludes_unincluded_items(client, cati_pdf_bytes) -> None:
    doc_id = _upload(client, cati_pdf_bytes)
    items = client.get(f"/api/v1/documents/{doc_id}/items").json()["items"]
    # Exclut le 1er article.
    client.patch(
        f"/api/v1/documents/{doc_id}/items/{items[0]['id']}",
        json={"included": False},
    )
    resp = client.get(f"/api/v1/documents/{doc_id}/export.xlsx")
    ws = openpyxl.load_workbook(io.BytesIO(resp.content))["Catalogue"]
    figs = [ws.cell(r, 3).value for r in range(1, ws.max_row + 1)]
    assert "10A" not in figs
    assert "20A" in figs
