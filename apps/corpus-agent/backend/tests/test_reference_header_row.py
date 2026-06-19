"""Choix de la ligne d'en-tête du référentiel.

Couvre le parser (`sheet_columns` override + `sheet_preview`) et le round-trip
API (persistance par onglet + fallback sur la ligne persistée).

Fixture 100 % synthétique : un classeur où l'en-tête (ligne 3) n'est PAS la
ligne la plus large — la détection auto tombe donc sur une ligne de données,
ce qui justifie le choix manuel.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.db.session import Base, engine
from app.main import create_app
from app.parsers.reference import sheet_columns, sheet_preview


def _make_workbook(tmp_path: Path) -> Path:
    """Onglet « ATM » :
    - ligne 1 : titre (1 cellule)
    - ligne 2 : vide
    - ligne 3 : EN-TÊTE voulu  -> ["Script", "Granule"]   (2 cellules)
    - lignes 4-5 : données plus larges (4 cellules) -> piègent la détection auto
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "ATM"
    ws.append(["Suivi ATM FTM"])
    ws.append([])
    ws.append(["Script", "Granule"])
    ws.append(["DMC-TG5-AB12", "G1", "extra", "more"])
    ws.append(["DMC-TG5-CD34", "G2", "foo", "bar"])
    dest = tmp_path / "ref.xlsx"
    wb.save(dest)
    return dest


# --------------------------- parser ---------------------------------------

def test_auto_detection_picks_widest_data_row(tmp_path: Path) -> None:
    path = str(_make_workbook(tmp_path))
    cols = sheet_columns(path, "ATM")  # sans override -> détection auto
    by_letter = {c["letter"]: c["header"] for c in cols}
    # La détection auto choisit la ligne la plus large (ligne 4 = données),
    # donc le libellé de A est une valeur de données, pas « Script ».
    assert by_letter["A"] == "DMC-TG5-AB12"


def test_header_row_override_reads_intended_header(tmp_path: Path) -> None:
    path = str(_make_workbook(tmp_path))
    cols = sheet_columns(path, "ATM", header_row=3)
    by_letter = {c["letter"]: c["header"] for c in cols}
    assert by_letter["A"] == "Script"
    assert by_letter["B"] == "Granule"
    # La largeur reste celle du scan complet (les données vont jusqu'à D).
    assert {"A", "B", "C", "D"} <= set(by_letter)


def test_header_row_out_of_range_falls_back_to_auto(tmp_path: Path) -> None:
    path = str(_make_workbook(tmp_path))
    cols = sheet_columns(path, "ATM", header_row=999)
    by_letter = {c["letter"]: c["header"] for c in cols}
    assert by_letter["A"] == "DMC-TG5-AB12"  # comme l'auto


def test_sheet_preview_returns_rows_and_detected(tmp_path: Path) -> None:
    path = str(_make_workbook(tmp_path))
    pv = sheet_preview(path, "ATM")
    assert pv["header_row_detected"] == 4  # 1-based, ligne de données la + large
    assert len(pv["rows"]) == 5
    assert pv["rows"][2][0] == "Script"  # ligne 3 (index 2)


def test_sheet_preview_missing_sheet(tmp_path: Path) -> None:
    path = str(_make_workbook(tmp_path))
    pv = sheet_preview(path, "INEXISTANT")
    assert pv == {"header_row_detected": 0, "rows": []}


# --------------------------- API round-trip --------------------------------

@pytest.fixture
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(create_app())


def _create_project(client: TestClient) -> str:
    r = client.post("/api/v1/projects", json={"name": f"P-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_reference(client: TestClient, pid: str, path: Path) -> None:
    with path.open("rb") as fh:
        r = client.post(
            f"/api/v1/projects/{pid}/reference",
            files={"file": ("ref.xlsx", fh,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 200, r.text


def test_mapping_persists_header_rows(client: TestClient, tmp_path: Path) -> None:
    pid = _create_project(client)
    _upload_reference(client, pid, _make_workbook(tmp_path))

    r = client.put(f"/api/v1/projects/{pid}/reference/mapping",
                   json={"columns": [], "header_rows": {"ATM": 3}})
    assert r.status_code == 200, r.text
    assert r.json()["header_rows"] == {"ATM": 3}

    # GET reference renvoie la ligne persistée.
    assert client.get(f"/api/v1/projects/{pid}/reference").json()["header_rows"] == {"ATM": 3}


def test_columns_endpoint_uses_persisted_header_row(client: TestClient, tmp_path: Path) -> None:
    pid = _create_project(client)
    _upload_reference(client, pid, _make_workbook(tmp_path))
    client.put(f"/api/v1/projects/{pid}/reference/mapping",
               json={"columns": [], "header_rows": {"ATM": 3}})

    # Sans header_row explicite -> la ligne persistée (3) est utilisée.
    cols = client.get(f"/api/v1/projects/{pid}/reference/columns",
                      params={"sheet": "ATM"}).json()
    assert {c["letter"]: c["header"] for c in cols}["A"] == "Script"

    # Override explicite a la priorité sur la valeur persistée.
    cols4 = client.get(f"/api/v1/projects/{pid}/reference/columns",
                       params={"sheet": "ATM", "header_row": 4}).json()
    assert {c["letter"]: c["header"] for c in cols4}["A"] == "DMC-TG5-AB12"


def test_preview_endpoint(client: TestClient, tmp_path: Path) -> None:
    pid = _create_project(client)
    _upload_reference(client, pid, _make_workbook(tmp_path))
    pv = client.get(f"/api/v1/projects/{pid}/reference/preview",
                    params={"sheet": "ATM"}).json()
    assert pv["header_row_detected"] == 4
    assert pv["rows"][2][0] == "Script"
