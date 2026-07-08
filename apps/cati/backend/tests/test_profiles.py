"""Tests - profils CATI (CRUD + application pdf_map/excel_map)."""

from __future__ import annotations

import io

import openpyxl

from app.core.catalogue_schema import item_to_row
from app.parsers.pdf_table import group_grid


def _grid_shuffled() -> list[list]:
    """Grille CATI avec DESIGNATION et SYMBOLE intervertis (colonnes 1 et 2)."""
    return [
        ["FIG REP", "COLB", "COLC", "IDENTIFICATION", "", "QUANTITE", "", "APP"],
        ["", "", "", "Code", "Reference", "ES", "EM", ""],
        ["10A", "sym1", ".Piece A", "Client", "C1", "1", "", ""],
        ["", "", "", "Interne", "I1", "", "", ""],
    ]


def test_group_grid_override_fixes_columns() -> None:
    # Sans override, "COLB"/"COLC" ne matchent pas designation -> description vide.
    base = group_grid(_grid_shuffled())
    assert base and base[0]["description"] == ""
    # Override : designation en colonne 2 (index 2).
    fixed = group_grid(_grid_shuffled(), override={"designation": 2})
    assert fixed[0]["description"] == "Piece A"


def test_item_to_row_excel_map_override() -> None:
    item = {"fig": "10A", "description": "Piece A", "ref_client": "C1"}
    # Redirige la description (F par defaut) vers la colonne matiere (G).
    row = item_to_row(item, {}, excel_map={"description": "matiere"})
    assert row["matiere"] == "Piece A"
    assert row["description"] is None


# ---- routes ----------------------------------------------------------------


def test_profile_crud_and_default(client) -> None:
    a = client.post("/api/v1/profiles", json={"name": "Fournisseur A", "pdf_map": {"designation": 2}}).json()
    assert a["is_default"] is True
    assert a["pdf_map"] == {"designation": 2}

    b = client.post("/api/v1/profiles", json={"name": "Fournisseur B"}).json()
    assert b["is_default"] is False

    nb = client.post(f"/api/v1/profiles/{b['id']}/default").json()
    assert nb["is_default"] is True

    up = client.put(
        f"/api/v1/profiles/{a['id']}",
        json={"name": "A modifie", "excel_map": {"description": "matiere"}},
    ).json()
    assert up["name"] == "A modifie"
    assert up["excel_map"] == {"description": "matiere"}

    client.delete(f"/api/v1/profiles/{b['id']}")
    remaining = client.get("/api/v1/profiles").json()
    assert len(remaining) == 1 and remaining[0]["is_default"] is True


def test_profile_rejects_unknown_fields(client) -> None:
    p = client.post(
        "/api/v1/profiles",
        json={"name": "P", "pdf_map": {"inconnu": 3, "fig": 0}, "excel_map": {"bidon": "x"}},
    ).json()
    assert p["pdf_map"] == {"fig": 0}  # champ inconnu filtre
    assert p["excel_map"] == {}


def test_upload_with_profile_applies_excel_map(client, cati_pdf_bytes) -> None:
    prof = client.post(
        "/api/v1/profiles",
        json={"name": "Redir", "excel_map": {"description": "matiere"}},
    ).json()

    resp = client.post(
        "/api/v1/documents",
        files=[("files", ("plan.pdf", cati_pdf_bytes, "application/pdf"))],
        data={"profile_id": prof["id"]},
    )
    doc_id = resp.json()["results"][0]["document_id"]
    assert client.get(f"/api/v1/documents/{doc_id}").json()["profile_id"] == prof["id"]

    xlsx = client.get(f"/api/v1/documents/{doc_id}/export.xlsx").content
    ws = openpyxl.load_workbook(io.BytesIO(xlsx))["Catalogue"]
    # description (Piece A) redirigee vers matiere (colonne G=7) au lieu de F=6.
    row2 = {c: ws.cell(2, c).value for c in range(1, 8)}
    assert row2[7] == "Piece A"   # G matiere
    assert row2[6] in (None, "")  # F description vide
