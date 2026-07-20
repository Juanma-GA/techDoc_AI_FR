"""Tests import checklist Excel : classification heuristique + mode remplacement."""

from __future__ import annotations

from tests.conftest import XLSX_MIME


def _import(client, data, mode=None):
    payload = {"file": ("c.xlsx", data, XLSX_MIME)}
    form = {"mode": mode} if mode else None
    return client.post("/api/v1/rules/import", files=payload, data=form)


def test_checklist_template_downloadable_and_reimportable(client):
    """Le modele fourni se telecharge et se reimporte : les regles « manuel »
    restent `manual` (verif humaine), les autres partent en `llm_nl`."""
    resp = client.get("/api/v1/rules/template")
    assert resp.status_code == 200, resp.text
    assert "spreadsheetml" in resp.headers["content-type"]
    r = _import(client, resp.content, mode="replace")
    assert r.status_code == 200
    by_kind = r.json()["by_kind"]
    assert by_kind.get("manual", 0) == 3  # bloc « verif manuel »
    assert by_kind.get("llm_nl", 0) == 3  # regles evaluees par l'IA


def test_import_manual_handling_column(client, make_checklist):
    """Une colonne « prise en compte » = manuel garde la regle en `manual`."""
    from openpyxl import Workbook
    import io

    wb = Workbook()
    ws = wb.active
    ws.append(["Topic", "Regles", "Type"])
    ws.append(["A", "Verifier a la main les notes", "manuel"])
    ws.append(["A", "Le titre doit etre en majuscules", "auto"])
    buf = io.BytesIO()
    wb.save(buf)
    r = _import(client, buf.getvalue(), mode="replace")
    assert r.status_code == 200
    kinds = {rule["kind"] for rule in client.get("/api/v1/rules").json()}
    assert "manual" in kinds and "llm_nl" in kinds


def test_import_sets_all_rules_to_llm(client, make_checklist):
    data = make_checklist(
        [
            ("General", "Header (logo, PNR)"),
            ("General", "Text must be justified"),
            ("General", "Revision bar next to the modified illustration"),
            ("Highlights", "Use compliant sentences according to the ATA100 model"),
        ]
    )
    r = _import(client, data)
    assert r.status_code == 200
    # Toutes les regles importees sont confiees au LLM (evaluation semantique).
    by_kind = r.json()["by_kind"]
    assert by_kind == {"llm_nl": 4}
    rules = client.get("/api/v1/rules").json()
    assert all(rule["kind"] == "llm_nl" for rule in rules)
    assert all(rule["pattern"] == "" for rule in rules)


def test_import_replaces_previous(client, make_checklist):
    _import(client, make_checklist([("A", "Check one"), ("A", "Check two")]))
    second = _import(client, make_checklist([("B", "Only one check")]))
    assert second.json()["replaced_count"] == 2
    rules = client.get("/api/v1/rules").json()
    assert len(rules) == 1
    assert rules[0]["name"] == "Only one check"


def _names(client):
    return sorted(r["name"] for r in client.get("/api/v1/rules").json())


def test_import_mode_add_skips_duplicates(client, make_checklist):
    _import(client, make_checklist([("A", "Check one")]))
    r = _import(client, make_checklist([("A", "Check one"), ("B", "Check two")]), mode="add")
    body = r.json()
    assert body["created"] == 1 and body["updated"] == 0 and body["skipped"] == ["Check one"]
    assert _names(client) == ["Check one", "Check two"]


def test_import_mode_update_only_existing(client, make_checklist):
    _import(client, make_checklist([("A", "Check one")]))
    r = _import(client, make_checklist([("A", "Check one"), ("B", "Check two")]), mode="update")
    body = r.json()
    assert body["created"] == 0 and body["updated"] == 1 and body["skipped"] == ["Check two"]
    assert _names(client) == ["Check one"]  # rien de cree


def test_import_mode_overwrite_upserts(client, make_checklist):
    _import(client, make_checklist([("A", "Check one")]))
    r = _import(client, make_checklist([("A", "Check one"), ("B", "Check two")]), mode="overwrite")
    body = r.json()
    assert body["created"] == 1 and body["updated"] == 1 and body["skipped"] == []
    assert _names(client) == ["Check one", "Check two"]


def test_import_bad_mode_rejected(client, make_checklist):
    r = _import(client, make_checklist([("A", "Check one")]), mode="bogus")
    assert r.status_code == 400


def test_classifier_generates_pattern(monkeypatch):
    # Exerce le chemin "Mistral configure" (skippe en prod sans cle) : verifie que
    # le classifieur produit une regle corrective + repli llm_nl. Garde le bug
    # 're' non importe / _KINDS incomplet de revenir.
    import asyncio

    from app.core import checklist_classifier as cc
    from app.core.excel_rules import ParsedRule

    class _Fake:
        async def chat(self, messages, **kw):
            return ('{"rules":[{"i":0,"kind":"regex_replace","pattern":"SEXTANT",'
                    '"replacement":"ACME","severity":"error"},'
                    '{"i":1,"kind":"term_replace","pattern":""}]}')

    monkeypatch.setattr(cc.MistralClient, "from_db", staticmethod(lambda db: _Fake()))
    mk = lambda n: ParsedRule(name=n, category="G", kind="llm_nl", pattern="", replacement="",
                              target_zone="", severity="warning", message=n)
    out, used = asyncio.run(cc.classify_rules(None, [mk("a"), mk("b")]))
    assert used is True
    assert out[0].kind == "regex_replace" and out[0].pattern == "SEXTANT" and out[0].replacement == "ACME"
    assert out[1].kind == "llm_nl"  # pattern vide -> repli


def test_llm_covers_all_chunks(monkeypatch):
    # Le passage LLM doit couvrir TOUT le document (un appel par morceau), pas
    # seulement les 30 premiers blocs / blocs modifies.
    import asyncio

    from app.core import llm_checks as lc
    from app.db.session import SessionLocal
    from app.parsers.docx_parser import Block, ParsedDocx

    blocks = [Block(target_id=f"dp{i+1}", index=i + 1, zone="body", kind="paragraph", text=f"para {i}") for i in range(25)]
    parsed = ParsedDocx(block_count=25, blocks=blocks, headers=[], footers=[], full_text="x")
    rules = [{"code": "CUSTOM_x", "kind": "llm_nl", "severity": "warning", "message": "m", "rule_kind": "custom", "target_zone": ""}]

    class _Fake:
        async def chat(self, messages, **kw):
            return '{"violations":[{"r":0,"b":0,"confidence":0.3,"reason":"x","proposed":""}]}'

    monkeypatch.setattr(lc.MistralClient, "from_db", staticmethod(lambda db: _Fake()))
    db = SessionLocal()
    out = asyncio.run(lc.run_llm(db, parsed, rules))
    db.close()
    # 25 blocs / chunk 12 = 3 morceaux -> 3 findings (1 par morceau), faible confiance -> info
    assert len(out) == 3 and all(o.severity == "info" for o in out)


def test_inspect_lists_sheets(client, make_checklist):
    r = client.post("/api/v1/rules/inspect", files={"file": ("c.xlsx", make_checklist([("G", "Check one")]), XLSX_MIME)})
    assert r.status_code == 200
    sheets = r.json()["sheets"]
    assert sheets and sheets[0]["rows"]  # grille d'apercu
    assert "header_row" in sheets[0] and isinstance(sheets[0]["header_row"], int)


def test_import_with_explicit_mapping(client):
    import io
    from openpyxl import Workbook

    wb = Workbook(); ws = wb.active
    ws.append(["ignore", "Rubrique", "Verification"])
    ws.append(["x", "General", "Header logo present"])
    buf = io.BytesIO(); wb.save(buf)
    r = client.post(
        "/api/v1/rules/import",
        files={"file": ("c.xlsx", buf.getvalue(), XLSX_MIME)},
        data={"topic_col": "1", "check_col": "2", "header_row": "0"},
    )
    assert r.status_code == 200 and r.json()["imported"] == 1
    rules = client.get("/api/v1/rules").json()
    assert rules[0]["category"] == "General"
    assert rules[0]["name"].startswith("Header logo present")


def test_imported_rules_pending_until_validated(client, make_checklist, make_docx, monkeypatch):
    from tests.conftest import DOCX_MIME

    # Les regles importees sont des llm_nl : on simule Mistral pour qu'elles surfacent.
    from app.core import llm_checks as lc

    class _Fake:
        async def chat(self, messages, **kw):
            return '{"violations":[{"r":0,"b":0,"confidence":0.9,"reason":"non conforme","proposed":"Corrige."}]}'

    monkeypatch.setattr(lc.MistralClient, "from_db", staticmethod(lambda db: _Fake()))

    _import(client, make_checklist([("General", "Logo positioning is correct")]))
    # Importee = en attente de validation (validated=False) : ne participe pas encore.
    assert all(r["validated"] is False for r in client.get("/api/v1/rules").json())
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", make_docx(["Body."]), DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    sug = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    assert not any(s["rule_kind"] == "custom" for s in sug)

    # Apres validation en bloc, la regle (llm_nl) surface via le LLM.
    n = client.post("/api/v1/rules/validate-all").json()["validated"]
    assert n >= 1
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    sug2 = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    assert any(s["rule_kind"] == "custom" for s in sug2)
