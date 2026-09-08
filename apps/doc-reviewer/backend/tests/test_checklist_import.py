"""Checklist import persists every compiled outcome with its execution state."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.api import rules as rules_api
from app.core.compiled_rules import Check, CompiledRule, RuleTarget


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


def test_import_keeps_unsupported_rows_visible(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/rules/import",
        files={"file": ("checklist.xlsx", _checklist_xlsx(), "application/vnd.ms-excel")},
        data={"mode": "replace"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported"] == 3
    assert body["by_kind"] == {"unsupported": 3}
    assert all(rule["execution"] == "unsupported" for rule in body["rules"])
    assert all(rule["active"] is False for rule in body["rules"])

    compiled = client.get("/api/v1/compiled-rules").json()
    checklist_rules = [rule for rule in compiled if rule["source"] == "user_checklist"]
    assert len(checklist_rules) == 3
    assert all(rule["execution"] == "unsupported" for rule in checklist_rules)


def test_deterministic_rule_is_active_immediately(client: TestClient, monkeypatch) -> None:
    def compile_deterministic(_db, row, filename: str) -> CompiledRule:
        return CompiledRule(
            id=f"compiled-{row.row_number}",
            topic=row.name,
            execution="deterministic",
            target=RuleTarget(page="all", region="full_page"),
            checks=[Check(field="text", operator="regex", expected="ATA")],
            source="user_checklist",
            origin_ref=f"{filename}:{row.sheet}:{row.row_number}",
        )

    monkeypatch.setattr(rules_api, "compile_checklist_rule", compile_deterministic)
    resp = client.post(
        "/api/v1/rules/import",
        files={"file": ("checklist.xlsx", _checklist_xlsx(), "application/vnd.ms-excel")},
        data={"mode": "replace"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["by_kind"] == {"deterministic": 3}
    assert all(rule["active"] is True for rule in body["rules"])


def test_compiled_standard_rules_are_filtered_by_selected_version(client: TestClient) -> None:
    from sqlalchemy import select

    from app.db.models import Standard, StandardVersion
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        ata_id = db.scalar(
            select(StandardVersion.id)
            .join(Standard)
            .where(Standard.code == "ATA100")
        )
        assert ata_id is not None
    finally:
        db.close()

    unscoped = client.get("/api/v1/compiled-rules")
    assert not any(rule["source"] == "standard_rule" for rule in unscoped.json())

    scoped = client.get(
        "/api/v1/compiled-rules",
        params={"standard_version_id": str(ata_id)},
    )
    standard_rules = [rule for rule in scoped.json() if rule["source"] == "standard_rule"]
    assert standard_rules
    assert all((rule["origin_ref"] or "").startswith("ATA100:") for rule in standard_rules)


def test_template_download(client: TestClient) -> None:
    resp = client.get("/api/v1/rules/template")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
