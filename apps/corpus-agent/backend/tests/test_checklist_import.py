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


def test_import_default_mode_is_non_destructive_upsert(client: TestClient) -> None:
    """Un appel qui OMET `mode` (Swagger, script direct, ancien client) ne doit
    jamais purger la checklist existante par defaut : le defaut cote API est
    "overwrite" (upsert), jamais "replace"."""
    _import(client, make_checklist([("A", "regle un")]))

    resp = client.post(
        "/api/v1/settings/rules/checklist/import",
        files={"file": ("c.xlsx", make_checklist([("A2", "regle un"), ("B", "regle deux")]),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        # `mode` volontairement absent du payload.
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["mode"] == "overwrite"
    assert result["created"] == 1
    assert result["updated"] == 1
    # Si le defaut avait glisse vers "replace", la regle "A" initiale aurait
    # disparu : la checklist doit au contraire s'etre enrichie, pas purgee.
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


def test_import_mapping_folds_unmapped_columns_and_skips_manual(client: TestClient) -> None:
    """Parité word-reviewer en mode mapping : la colonne « prise en compte »
    filtre les lignes manuelles, et toute colonne NON mappée (ici « Reference »)
    est ajoutée au texte de la règle."""
    wb = Workbook()
    ws = wb.active
    ws.title = "CL"
    ws.append(["Sujet", "Verification", "Prise en compte", "Reference"])
    ws.append(["Securite", "Doit mentionner les EPI", "auto", "DOC-1"])
    ws.append(["Manuel", "Verification a la main", "manuel", "DOC-2"])
    buf = io.BytesIO()
    wb.save(buf)

    resp = client.post(
        "/api/v1/settings/rules/checklist/import",
        files={"file": ("c.xlsx", buf.getvalue(), "application/octet-stream")},
        data={
            "header_row": 0, "topic_col": 0, "check_col": 1,
            "handling_col": 2, "mode": "replace",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 1  # ligne « manuel » ignorée
    rules = _custom_rules()
    assert len(rules) == 1
    # La colonne « Reference » (non mappée) est repliée dans le texte de la règle.
    assert "DOC-1" in rules[0]["consigne"]
    assert rules[0]["label"] == "Securite"


def test_import_mapping_zone_excluded_and_explicit_context(client: TestClient) -> None:
    """Zone mappée -> exclue du texte de la règle (métadonnée). Contexte explicite
    -> seule cette colonne est repliée (override de l'auto-contexte)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "CL"
    ws.append(["Sujet", "Verification", "Zone", "Contexte", "Autre"])
    ws.append(["Securite", "Doit mentionner les EPI", "ZONEVAL", "CONTEXTEVAL", "AUTREVAL"])
    buf = io.BytesIO()
    wb.save(buf)

    resp = client.post(
        "/api/v1/settings/rules/checklist/import",
        files={"file": ("c.xlsx", buf.getvalue(), "application/octet-stream")},
        data={
            "header_row": 0, "topic_col": 0, "check_col": 1,
            "zone_col": 2, "context_cols": "[3]", "mode": "replace",
        },
    )
    assert resp.status_code == 200, resp.text
    rules = _custom_rules()
    assert len(rules) == 1
    consigne = rules[0]["consigne"]
    assert "CONTEXTEVAL" in consigne      # contexte explicite inclus
    assert "ZONEVAL" not in consigne      # zone exclue
    assert "AUTREVAL" not in consigne     # « Autre » exclue (contexte explicite -> override)


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


def test_auto_detect_finds_checklist_on_non_first_sheet(client: TestClient) -> None:
    """Auto-detection : la checklist n'est pas sur le 1er onglet (onglet de garde
    devant). L'import doit scanner tous les onglets et trouver les regles."""
    wb = Workbook()
    cover = wb.active
    cover.title = "Couverture"
    cover.append(["Document", "FTM 123"])
    cover.append(["Version", "B"])
    ws = wb.create_sheet("Regles")
    ws.append(["Sujet", "Verification"])
    ws.append(["Securite", "Chaque tache dangereuse doit mentionner les EPI"])
    ws.append(["Redaction", "Les phrases doivent etre a l'imperatif"])
    buf = io.BytesIO()
    wb.save(buf)
    result = _import(client, buf.getvalue())
    assert result["created"] == 2
    assert {r["label"] for r in _custom_rules()} == {"Securite", "Redaction"}


def test_auto_detect_recognizes_french_headers(client: TestClient) -> None:
    """En-tetes FR elargis : « Domaine » / « Critere » sont reconnus."""
    wb = Workbook()
    ws = wb.active
    ws.title = "CL"
    ws.append(["Domaine", "Critere"])
    ws.append(["Securite", "Doit mentionner les EPI"])
    buf = io.BytesIO()
    wb.save(buf)
    result = _import(client, buf.getvalue())
    assert result["created"] == 1
    assert _custom_rules()[0]["label"] == "Securite"


def test_auto_detect_ignores_title_row_containing_a_role_keyword(client: TestClient) -> None:
    """Regression : un titre de document contenant « check » (ou tout autre mot
    d'alias) ne doit pas etre pris pour l'en-tete. Avant le score par nombre de
    roles, la ligne 1 gagnait avec le seul role « check » -> l'en-tete reelle et
    le sous-titre devenaient des regles, et les labels tombaient sur le defaut."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Check-list qualite"
    ws.append(["CHECK-LIST QUALITE - REVUE DOCUMENTAIRE"])  # capte « check »
    ws.append(["Emission du 27/07/2026"])
    ws.append([])
    ws.append(["Sujet", "Verification", "Criticite"])  # vraie en-tete (3 roles)
    ws.append(["Titre", "Le document comporte un titre explicite", "majeur"])
    ws.append(["Unites", "Les valeurs numeriques portent leur unite SI", "mineur"])
    buf = io.BytesIO()
    wb.save(buf)

    result = _import(client, buf.getvalue())

    assert result["created"] == 2, "le sous-titre et l'en-tete ne sont plus des regles"
    rules = _custom_rules()
    assert {r["label"] for r in rules} == {"Titre", "Unites"}
    assert {r["severity"] for r in rules} == {"high", "low"}


def test_inspect_exposes_roles_so_ui_opens_the_right_sheet(client: TestClient) -> None:
    """`inspect` expose les colonnes reconnues par onglet : l'UI ouvre l'onglet
    checklist (pas la page de garde) avec le bon mapping."""
    wb = Workbook()
    cover = wb.active
    cover.title = "Page de garde"
    cover.append(["Document interne"])
    ws = wb.create_sheet("Check-list")
    ws.append(["CHECK-LIST QUALITE - REVUE"])
    ws.append([])
    ws.append(["Sujet", "Verification", "Criticite"])
    ws.append(["Titre", "Le document comporte un titre explicite", "majeure"])
    buf = io.BytesIO()
    wb.save(buf)

    resp = client.post(
        "/api/v1/settings/rules/checklist/inspect",
        files={"file": ("cl.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    sheets = resp.json()["sheets"]

    assert sheets[0]["roles"] is None, "la page de garde n'est pas une checklist"
    checklist = sheets[1]
    assert checklist["roles"] == {"topic": 0, "check": 1, "severity": 2}
    assert checklist["header_row"] == 2, "en-tete reelle, pas la ligne de titre"


def test_import_maps_feminine_severity_spellings(client: TestClient) -> None:
    """Regression : « majeure » / « mineure » (accord avec « criticite », nom
    feminin) doivent mapper comme « majeur » / « mineur ». Le lookup exact les
    ratait et tout retombait sur le defaut medium."""
    wb = Workbook()
    ws = wb.active
    ws.title = "CL"
    ws.append(["Sujet", "Verification", "Criticite"])
    ws.append(["Titre", "Le document comporte un titre explicite", "majeure"])
    ws.append(["Unites", "Les valeurs numeriques portent leur unite SI", "mineure"])
    ws.append(["Style", "Le ton reste neutre", "moyenne"])
    buf = io.BytesIO()
    wb.save(buf)

    result = _import(client, buf.getvalue())

    assert result["created"] == 3
    assert {r["label"]: r["severity"] for r in _custom_rules()} == {
        "Titre": "high", "Unites": "low", "Style": "medium",
    }


def test_auto_detect_heuristic_without_recognized_headers(client: TestClient) -> None:
    """Aucun en-tete reconnu : repli heuristique -> la colonne au texte le plus
    long devient la « verification »."""
    wb = Workbook()
    ws = wb.active
    ws.title = "X"
    ws.append(["Ref", "Detail"])  # en-tetes non mappes
    ws.append(["S1", "Une verification longue decrivant precisement un point a controler"])
    ws.append(["S2", "Autre verification detaillee sur un element du livrable technique"])
    buf = io.BytesIO()
    wb.save(buf)
    result = _import(client, buf.getvalue())
    assert result["created"] == 2
    consignes = [r["consigne"] for r in _custom_rules()]
    assert any("verification longue" in c for c in consignes)


def test_load_wb_falls_back_to_normal_mode_when_readonly_sees_no_sheet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Certains classeurs (relations non standard) ne remontent AUCUN onglet en
    mode read_only streaming -> `inspect OK — 0 onglet(s)`. Le loader doit
    retomber sur le mode normal, qui, lui, voit les onglets."""
    import app.core.checklist_excel as mod

    wb = Workbook()
    ws = wb.active
    ws.title = "CL"
    ws.append(["Sujet", "Verification"])
    ws.append(["Securite", "Doit mentionner les EPI"])
    buf = io.BytesIO()
    wb.save(buf)
    data = buf.getvalue()

    real_load = mod.load_workbook

    class _EmptyWB:
        worksheets: list = []

        def close(self) -> None:
            pass

    def fake_load(*args, **kwargs):
        # Mode read_only -> simule « aucun onglet » ; mode normal -> vrai classeur.
        if kwargs.get("read_only"):
            return _EmptyWB()
        return real_load(*args, **kwargs)

    monkeypatch.setattr(mod, "load_workbook", fake_load)

    assert len(mod.list_sheets(data)) == 1          # inspect voit l'onglet
    rules = mod.parse_checklist(data, mapping=None)  # import trouve la regle
    assert len(rules) == 1
    assert rules[0].label == "Securite"


def test_load_wb_normalizes_via_libreoffice_when_openpyxl_sees_no_sheet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fichier « Strict Open XML » / export exotique : openpyxl ne voit AUCUN
    onglet dans les DEUX modes -> on doit passer par la normalisation LibreOffice
    puis relire le résultat."""
    import app.core.checklist_excel as mod

    wb = Workbook()
    ws = wb.active
    ws.title = "CL"
    ws.append(["Sujet", "Verification"])
    ws.append(["Securite", "Doit mentionner les EPI"])
    buf = io.BytesIO()
    wb.save(buf)
    normalized_bytes = buf.getvalue()

    real_load = mod.load_workbook
    calls = {"n": 0}

    class _EmptyWB:
        worksheets: list = []

        def close(self) -> None:
            pass

    def fake_load(bio, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:  # les 2 tentatives openpyxl sur le fichier d'origine
            return _EmptyWB()
        return real_load(bio, **kwargs)  # relecture après normalisation

    monkeypatch.setattr(mod, "load_workbook", fake_load)
    monkeypatch.setattr(mod, "normalize_xlsx_bytes", lambda data: normalized_bytes)

    assert len(mod.list_sheets(b"strict-ooxml")) == 1
    rules = mod.parse_checklist(b"strict-ooxml", mapping=None)
    assert len(rules) == 1
    assert rules[0].label == "Securite"


def test_parse_checklist_falls_back_when_active_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Certains .xlsx/.xlsm exportes par d'autres outils ont `wb.active == None`
    (onglet actif non defini). Sans onglet precise (import direct), parse doit
    se rabattre sur le premier onglet au lieu de crasher (bug historique :
    'NoneType' object has no attribute 'iter_rows')."""
    import app.core.checklist_excel as mod

    class _FakeWS:
        def iter_rows(self, values_only: bool = False):  # noqa: ARG002
            return iter([("Topic", "Check"), ("Securite", "Une regle de controle")])

    class _FakeWB:
        active = None  # <- le cas qui plantait
        worksheets = [_FakeWS()]
        sheetnames = ["Checklist"]

        def __getitem__(self, name):  # noqa: ANN001, ARG002
            return self.worksheets[0]

        def close(self) -> None:
            pass

    monkeypatch.setattr(mod, "load_workbook", lambda *a, **k: _FakeWB())
    rules = mod.parse_checklist(b"ignored", sheet=None, mapping=None)
    assert len(rules) == 1
    assert rules[0].consigne == "Une regle de controle"


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
