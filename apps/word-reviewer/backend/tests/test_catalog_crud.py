"""Tests CRUD du catalogue ATA100 (regles builtin editables) + toggle + reset."""

from __future__ import annotations

from tests.conftest import DOCX_MIME


def _ata(client):
    standards = client.get("/api/v1/standards").json()
    ata = next(s for s in standards if s["code"] == "ATA100")
    return ata["id"], ata["versions"][0]["id"]


def _base(client):
    sid, vid = _ata(client)
    return f"/api/v1/standards/{sid}/versions/{vid}"


def test_version_detail_lists_catalog(client):
    detail = client.get(_base(client)).json()
    assert detail["catalog"]
    assert any(r["code"] == "ATA_CHAPTER_REF" for r in detail["catalog"])
    # chaque regle expose une source affichable (groupement UI)
    assert all(r["source"] for r in detail["catalog"])
    assert "ATA 100" in {r["source"] for r in detail["catalog"]}


def test_add_catalog_rule_fires_in_analysis(client, make_docx):
    base = _base(client)
    add = client.post(base + "/rules", json={
        "code": "TEST_FOOBAR", "title": "Foobar flag", "kind": "regex_flag",
        "severity": "warning", "pattern": r"FOOBAR\d+", "message": "Foobar detecte.",
    })
    assert add.status_code == 200
    assert any(r["code"] == "TEST_FOOBAR" for r in add.json()["catalog"])

    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", make_docx(["Token FOOBAR42 here."]), DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    codes = {s["rule_code"] for s in client.get(f"/api/v1/documents/{doc_id}/suggestions").json()}
    assert "TEST_FOOBAR" in codes


def test_patch_and_bad_pattern(client):
    base = _base(client)
    r = client.patch(base + "/rules/TEST_FOOBAR", json={"severity": "error"})
    assert r.status_code == 200
    assert next(x for x in r.json()["catalog"] if x["code"] == "TEST_FOOBAR")["severity"] == "error"
    bad = client.patch(base + "/rules/TEST_FOOBAR", json={"pattern": "("})
    assert bad.status_code == 400


def test_toggle_disables_rule(client, make_docx):
    base = _base(client)
    client.post(base + "/rules/toggle", json={"code": "TEST_FOOBAR", "enabled": False})
    detail = client.get(base).json()
    assert "TEST_FOOBAR" in detail["disabled_rule_codes"]
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", make_docx(["FOOBAR99 token."]), DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    codes = {s["rule_code"] for s in client.get(f"/api/v1/documents/{doc_id}/suggestions").json()}
    assert "TEST_FOOBAR" not in codes


def test_delete_then_reset(client):
    base = _base(client)
    d = client.delete(base + "/rules/TEST_FOOBAR")
    assert d.status_code == 200
    assert not any(r["code"] == "TEST_FOOBAR" for r in d.json()["catalog"])
    # reset restaure le catalogue d'usine (regles ATA100 presentes, disabled vide)
    reset = client.post(base + "/reset").json()
    assert any(r["code"] == "ATA_CHAPTER_REF" for r in reset["catalog"])
    assert reset["disabled_rule_codes"] == []
