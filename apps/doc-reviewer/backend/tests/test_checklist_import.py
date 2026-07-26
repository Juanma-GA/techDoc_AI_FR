"""Import checklist Excel -> regles llm_nl desactivees + activation en masse."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from openpyxl import Workbook


def _checklist_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Topic", "Check"])
    ws.append(["Copyright", "Le pied de page mentionne la raison sociale a jour"])
    ws.append(["Illustration", "Chaque figure porte un logo"])  # -> manual (visuel), ignore
    ws.append(["Reference", "La reference ATA est presente et coherente"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_import_creates_disabled_llm_rules(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/rules/import",
        files={"file": ("checklist.xlsx", _checklist_xlsx(), "application/vnd.ms-excel")},
        data={"mode": "replace"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported"] >= 1
    assert body["by_kind"].get("llm_nl", 0) >= 1

    rules = client.get("/api/v1/rules").json()
    llm_rules = [r for r in rules if r["kind"] == "llm_nl"]
    assert llm_rules, "au moins une regle llm_nl importee"
    # Importees desactivees : elles n'atteignent le LLM qu'apres activation.
    assert all(r["enabled"] is False for r in llm_rules)


def test_validate_all_enables_imported_rules(client: TestClient) -> None:
    client.post(
        "/api/v1/rules/import",
        files={"file": ("checklist.xlsx", _checklist_xlsx(), "application/vnd.ms-excel")},
        data={"mode": "replace"},
    )
    resp = client.post("/api/v1/rules/validate-all")
    assert resp.status_code == 200
    assert resp.json()["activated"] >= 1

    rules = client.get("/api/v1/rules").json()
    llm_rules = [r for r in rules if r["kind"] == "llm_nl"]
    assert all(r["enabled"] is True for r in llm_rules)


def test_template_download(client: TestClient) -> None:
    resp = client.get("/api/v1/rules/template")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
