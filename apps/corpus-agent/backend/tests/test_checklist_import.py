"""Import d'une checklist Excel dans les regles personnalisees.

Couvre : le parsing/mapping, les 4 modes (replace/add/update/overwrite), la
file de validation (regle importee = `validated:false`, exclue de l'analyse
jusqu'a validation), et `validate-all`.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.rules import load_rules, reset_rules
from app.db.session import Base, engine
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_rules()  # repart des defauts (pas de rules.json residuel entre tests)
    yield TestClient(create_app())
    reset_rules()


def make_checklist(rows: list[tuple[str, str]]) -> bytes:
    """Classeur .xlsx minimal : en-tete `Topic | Check` + lignes fournies."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Checklist"
    ws.append(["Topic", "Check"])
    for topic, check in rows:
        ws.append([topic, check])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _import(client: TestClient, data: bytes, mode: str = "replace") -> dict:
    resp = client.post(
        "/api/v1/settings/rules/checklist/import",
        files={"file": ("checklist.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"mode": mode},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _custom_rules() -> list[dict]:
    return [r for r in (load_rules().get("regles_personnalisees") or []) if isinstance(r, dict)]


def test_import_creates_pending_custom_rules(client: TestClient) -> None:
    data = make_checklist([
        ("Securite", "Chaque tache dangereuse doit mentionner les EPI"),
        ("Redaction", "Les phrases devraient etre a l'imperatif"),
        ("References", "Toute reference croisee doit exister"),
    ])
    result = _import(client, data)
    assert result["created"] == 3
    assert result["imported"] == 3
    assert result["pending"] == 3
    rules = _custom_rules()
    assert len(rules) == 3
    # File de validation : tout arrive non valide.
    assert all(r["validated"] is False for r in rules)
    assert all(r["consigne"] for r in rules)


def test_import_replace_purges_previous(client: TestClient) -> None:
    _import(client, make_checklist([("A", "regle un"), ("B", "regle deux")]))
    result = _import(client, make_checklist([("C", "regle trois")]))
    assert result["replaced_count"] == 2
    assert result["created"] == 1
    assert len(_custom_rules()) == 1


def test_import_mode_add_skips_duplicates(client: TestClient) -> None:
    _import(client, make_checklist([("A", "regle un")]))
    result = _import(client, make_checklist([("A", "regle un"), ("B", "regle deux")]), mode="add")
    assert result["created"] == 1
    assert result["updated"] == 0
    assert result["skipped"] == ["A"]
    assert len(_custom_rules()) == 2


def test_import_mode_update_only_existing(client: TestClient) -> None:
    _import(client, make_checklist([("A", "regle un")]))
    result = _import(
        client,
        make_checklist([("A-modifie", "regle un"), ("B", "regle deux")]),
        mode="update",
    )
    assert result["created"] == 0
    assert result["updated"] == 1
    assert result["skipped"] == ["B"]
    rules = _custom_rules()
    assert len(rules) == 1
    assert rules[0]["label"] == "A-modifie"


def test_import_mode_overwrite_upserts(client: TestClient) -> None:
    _import(client, make_checklist([("A", "regle un")]))
    result = _import(
        client,
        make_checklist([("A2", "regle un"), ("B", "regle deux")]),
        mode="overwrite",
    )
    assert result["created"] == 1
    assert result["updated"] == 1
    assert result["skipped"] == []
    assert len(_custom_rules()) == 2


def test_import_bad_mode_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/settings/rules/checklist/import",
        files={"file": ("c.xlsx", make_checklist([("A", "x")]), "application/octet-stream")},
        data={"mode": "nope"},
    )
    assert resp.status_code == 400


def test_import_bad_format_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/settings/rules/checklist/import",
        files={"file": ("c.txt", b"not excel", "text/plain")},
        data={"mode": "replace"},
    )
    assert resp.status_code == 400


def test_template_downloadable_and_reimportable(client: TestClient) -> None:
    """Le modele fourni se telecharge et se reimporte tel quel (5 regles)."""
    resp = client.get("/api/v1/settings/rules/checklist/template")
    assert resp.status_code == 200, resp.text
    assert "spreadsheetml" in resp.headers["content-type"]
    result = _import(client, resp.content)
    assert result["created"] == 5
    assert result["pending"] == 5


def test_import_skips_manual_rows(client: TestClient) -> None:
    """corpus-agent n'evalue que par IA : une ligne « manuel » (colonne Type)
    est ignoree a l'import ; la ligne « auto » est gardee."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Checklist"
    ws.append(["Sujet", "Verification", "Type"])
    ws.append(["A", "Regle evaluee par IA", "auto"])
    ws.append(["A", "Verification humaine a la main", "manuel"])
    buf = io.BytesIO()
    wb.save(buf)
    result = _import(client, buf.getvalue())
    assert result["created"] == 1
    rules = _custom_rules()
    assert len(rules) == 1
    assert rules[0]["consigne"] == "Regle evaluee par IA"


def test_inspect_lists_sheets(client: TestClient) -> None:
    data = make_checklist([("A", "regle un")])
    resp = client.post(
        "/api/v1/settings/rules/checklist/inspect",
        files={"file": ("c.xlsx", data, "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sheets"], "au moins un onglet"
    assert isinstance(body["sheets"][0]["header_row"], int)
    assert body["sheets"][0]["rows"]


def test_validate_all_clears_the_queue(client: TestClient) -> None:
    _import(client, make_checklist([("A", "regle un"), ("B", "regle deux")]))
    resp = client.post("/api/v1/settings/rules/validate-all")
    assert resp.status_code == 200
    assert resp.json()["validated"] == 2
    assert all(r["validated"] is True for r in _custom_rules())


def test_pending_rules_excluded_from_analysis_until_validated(client: TestClient) -> None:
    """Une regle importee (validated=False) ne doit pas etre chargee par le
    check custom_rules ; apres validate-all, elle l'est."""
    from app.checks.custom_rules import _load_custom_rules

    _import(client, make_checklist([("A", "une regle de controle")]))
    assert _load_custom_rules() == []  # en attente -> exclue

    client.post("/api/v1/settings/rules/validate-all")
    loaded = _load_custom_rules()
    assert len(loaded) == 1
    assert loaded[0]["consigne"] == "une regle de controle"
