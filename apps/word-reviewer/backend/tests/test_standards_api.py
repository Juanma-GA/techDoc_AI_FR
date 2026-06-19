"""Tests route standards : ATA100 builtin present par defaut, aucune regle custom seedee."""

from __future__ import annotations


def test_only_ata100_by_default(client):
    standards = client.get("/api/v1/standards").json()
    codes = {s["code"] for s in standards}
    assert codes == {"ATA100"}
    ata = next(s for s in standards if s["code"] == "ATA100")
    assert ata["builtin"] is True
    assert ata["versions"] and ata["versions"][0]["rule_count"] > 0


def test_no_custom_rules_by_default(client):
    # La table Rule reste vide tant que l'utilisateur n'a pas importe sa checklist.
    client.post("/api/v1/admin/reset/rules")
    assert client.get("/api/v1/rules").json() == []
