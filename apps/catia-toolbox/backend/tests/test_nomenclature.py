"""Tests Etape 1 - nomenclature .xlsx (fixtures synthetiques).

Le listing d'un DE .zip est desormais unifie sous /imports/zip (cf. test_imports).
"""

from __future__ import annotations

from openpyxl import Workbook


def _set_input_root(client, root: str) -> None:
    assert client.post("/api/v1/settings", json={"onedrive_input_root": root}).status_code == 200


def _make_xlsx(tmp_path):
    """Nomenclature synthetique (aucune donnee reelle)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Nomenclature"
    ws.append(["Titre du document", None, None, None, None, None])  # ligne parasite
    ws.append(["CATPart", "Designation", "SIN", "Version", "A traiter", "Couleur"])
    ws.append(["PIECE_001.CATPart", "Support avant", "SIN-001", "U320 n", "x", "rouge"])
    ws.append(["PIECE_002.CATPart", "Carter", "SIN-002", "U320 n", "", "0,128,255"])
    ws.append(["PIECE_003.CATPart", "Bielle", "SIN-003", "U320 n-1", "oui", ""])
    p = tmp_path / "nomenclature.xlsx"
    wb.save(p)
    return p


def test_parse_nomenclature(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)
    r = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(xlsx)})
    assert r.status_code == 200, r.text
    body = r.json()
    s = body["summary"]
    assert s["rows"] == 3
    assert s["to_treat"] == 2  # PIECE_001 (x) + PIECE_003 (oui)
    assert s["mono_color"] == 2  # rouge + 0,128,255
    assert "catpart" in s["detected_columns"]

    run_id = body["id"]
    items = client.get(f"/api/v1/identification/{run_id}/items", params={"to_treat": True}).json()
    assert {i["catpart"] for i in items} == {"PIECE_001.CATPart", "PIECE_003.CATPart"}

    mono = client.get(f"/api/v1/identification/{run_id}/items", params={"mono_color": True}).json()
    red = next(i for i in mono if i["sin"] == "SIN-001")
    assert (red["color_r"], red["color_g"], red["color_b"]) == (255, 0, 0)


def test_parse_with_manual_mapping(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)  # en-tete ligne 2 ; cols: 0 CATPart,2 SIN,4 A traiter,5 Couleur
    # Mapping explicite : on designe CATPart=col0, SIN=col2, couleur=col5, sans "a traiter".
    r = client.post("/api/v1/identification/nomenclature", json={
        "scope": "input", "path": str(xlsx),
        "mapping": {"header_row": 2, "catpart": 0, "sin": 2, "color": 5},
    })
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert s["manual_mapping"] is True
    assert s["rows"] == 3
    assert s["to_treat"] == 0  # colonne 'a traiter' non mappee -> tout False
    assert s["mono_color"] == 2

    run_id = r.json()["id"]
    items = client.get(f"/api/v1/identification/{run_id}/items").json()
    # CATPart vient bien de la colonne 0.
    assert {i["catpart"] for i in items} == {"PIECE_001.CATPart", "PIECE_002.CATPart", "PIECE_003.CATPart"}


def test_parse_mapping_requires_identity(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)
    # CATPart n'est plus obligatoire : une identite SIN suffit -> 200.
    ok = client.post("/api/v1/identification/nomenclature", json={
        "scope": "input", "path": str(xlsx), "mapping": {"header_row": 2, "sin": 2},
    })
    assert ok.status_code == 200, ok.text

    # Aucune colonne d'identite (ni CATPart, ni SIN, ni PN) -> 400.
    ko = client.post("/api/v1/identification/nomenclature", json={
        "scope": "input", "path": str(xlsx), "mapping": {"header_row": 2, "designation": 1},
    })
    assert ko.status_code == 400
    assert ko.json()["code"] == "MAPPING_NO_IDENTITY"


def test_preview_exposes_columns_map(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)
    r = client.post("/api/v1/identification/preview", json={"scope": "input", "path": str(xlsx)})
    cm = r.json()["columns_map"]
    assert cm["catpart"] == 0 and cm["sin"] == 2


def test_export_csv(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx(tmp_path)
    run_id = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(xlsx)}).json()["id"]
    r = client.get(f"/api/v1/identification/{run_id}/export.csv", params={"to_treat": True})
    assert r.status_code == 200
    assert r.text.splitlines()[0].startswith("catpart;")
    assert "PIECE_001.CATPart" in r.text


def test_nomenclature_rejects_outside_root(client, tmp_path):
    _set_input_root(client, str(tmp_path / "sub"))
    (tmp_path / "sub").mkdir()
    xlsx = _make_xlsx(tmp_path)  # hors racine
    r = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(xlsx)})
    assert r.status_code == 400
    assert r.json()["code"] == "PATH_OUTSIDE_ROOT"


def test_preview_sheets_and_rows(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    # Classeur a 2 onglets : la nomenclature est sur le 2eme.
    wb = Workbook()
    wb.active.title = "Garde"
    wb.active.append(["Page de garde"])
    ws2 = wb.create_sheet("BD Gestion")
    ws2.append(["Titre", None])
    ws2.append(["CATPart", "SIN", "Couleur"])
    ws2.append(["PIECE_001.CATPart", "SIN-001", "rouge"])
    p = tmp_path / "multi.xlsx"
    wb.save(p)

    # Apercu onglet par defaut (1er).
    r = client.post("/api/v1/identification/preview", json={"scope": "input", "path": str(p)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sheets"] == ["Garde", "BD Gestion"]
    assert body["sheet"] == "Garde"

    # Apercu de l'onglet choisi -> header detecte ligne 2, colonnes reconnues, grille.
    r2 = client.post("/api/v1/identification/preview", json={"scope": "input", "path": str(p), "sheet": "BD Gestion"})
    b2 = r2.json()
    assert b2["sheet"] == "BD Gestion"
    assert b2["header_row_detected"] == 2
    assert "catpart" in b2["columns_detected"]
    assert b2["rows"][1][0] == "CATPart"  # 2eme ligne = en-tete

    # Analyser en designant l'onglet.
    run = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p), "sheet": "BD Gestion"}).json()
    assert run["sheet"] == "BD Gestion"
    assert run["summary"]["rows"] == 1


def test_all_rows_and_to_treat_non_empty(client, tmp_path):
    """Prend toutes les lignes mappees ; 'a traiter' = colonne A TRAITER non vide."""
    _set_input_root(client, str(tmp_path))
    wb = Workbook()
    ws = wb.active
    ws.append(["CATPart", "SIN", "A traiter", "NEW P/N"])
    ws.append(["P1.CATPart", "SIN-1", "MODIF", "AA"])   # A traiter renseigne (valeur libre)
    ws.append(["", "SIN-2", "DEPLACE", "BB"])            # pas de CATPart -> quand meme pris
    ws.append(["P3.CATPart", "SIN-3", "", "CC"])          # A traiter vide -> pas a traiter
    ws.append(["", "", "", ""])                           # ligne vide -> ignoree
    p = tmp_path / "libre.xlsx"
    wb.save(p)

    body = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()
    run_id = body["id"]
    assert body["summary"]["rows"] == 3          # la ligne vide est la seule ecartee
    assert body["summary"]["to_treat"] == 2      # MODIF + DEPLACE (non vides), pas la 3e

    allrows = client.get(f"/api/v1/identification/{run_id}/items").json()
    by_sin = {i["sin"]: i for i in allrows}
    assert set(by_sin) == {"SIN-1", "SIN-2", "SIN-3"}   # la ligne sans CATPart (SIN-2) est bien la
    # La valeur brute de la cellule A TRAITER est conservee (affichage / controle).
    assert by_sin["SIN-1"]["to_treat_value"] == "MODIF"
    assert by_sin["SIN-2"]["to_treat_value"] == "DEPLACE"
    assert by_sin["SIN-3"]["to_treat_value"] == ""

    to_treat = client.get(f"/api/v1/identification/{run_id}/items", params={"to_treat": True}).json()
    assert {i["sin"] for i in to_treat} == {"SIN-1", "SIN-2"}

def test_x000_filters_optimized_parts(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    wb = Workbook()
    ws = wb.active
    ws.append(["CATPart", "SIN", "X000"])
    ws.append(["P1.CATPart", "SIN-1", "x"])
    ws.append(["P2.CATPart", "SIN-2", ""])
    ws.append(["P3.CATPart", "SIN-3", "oui"])
    xlsx = tmp_path / "optimized.xlsx"
    wb.save(xlsx)

    response = client.post(
        "/api/v1/identification/nomenclature",
        json={"scope": "input", "path": str(xlsx)},
    )
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["summary"]["optimized"] == 1
    assert "optimized" in run["summary"]["detected_columns"]

    items = client.get(
        f"/api/v1/identification/{run['id']}/items",
        params={"optimized": True},
    ).json()
    assert {item["sin"] for item in items} == {"SIN-1"}

    exported = client.get(
        f"/api/v1/identification/{run['id']}/export.csv",
        params={"optimized": True},
    )
    assert "P1.CATPart" in exported.text
    assert "P2.CATPart" not in exported.text


def _make_xlsx_full(tmp_path, name="nomen_full.xlsx"):
    """Nomenclature avec les colonnes remplacement + ref couleur + materiaux."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Nomenclature"
    ws.append([
        "CATPart", "Designation", "SIN", "A traiter",
        "OLD P/N", "NEW P/N", "OLD REV", "NEW REV", "Ref Couleur", "Couleur", "Materiaux",
    ])
    # Piece remplacee (old != new) + ref couleur "Visserie", pas de RGB, materiaux vide -> simple.
    ws.append(["P1.CATPart", "Vis", "SIN-001", "x", "AA-100", "AA-200", "A", "B", "Visserie", "", ""])
    # Non remplacee, RGB renseigne, materiaux renseigne (piece complexe multi-corps).
    ws.append(["P2.CATPart", "Carter", "SIN-002", "x", "", "", "", "", "", "255,0,0", "Aluminium"])
    p = tmp_path / name
    wb.save(p)
    return p


def test_replacement_and_refcolor_columns(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    xlsx = _make_xlsx_full(tmp_path)
    body = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(xlsx)}).json()
    assert body["summary"]["replaced"] == 1
    run_id = body["id"]

    items = {i["catpart"]: i for i in client.get(f"/api/v1/identification/{run_id}/items").json()}
    p1 = items["P1.CATPart"]
    assert p1["replaced"] is True
    assert p1["old_pn"] == "AA-100" and p1["new_pn"] == "AA-200"
    assert p1["old_rev"] == "A" and p1["new_rev"] == "B"
    assert p1["color_ref"] == "Visserie"
    assert p1["materials"] == ""

    # Filtre pieces remplacees.
    only_replaced = client.get(f"/api/v1/identification/{run_id}/items", params={"replaced": True}).json()
    assert {i["catpart"] for i in only_replaced} == {"P1.CATPart"}

    # Filtre par couleur (P2 a un RGB non nul).
    colored = client.get(f"/api/v1/identification/{run_id}/items", params={"has_color": True}).json()
    assert {i["catpart"] for i in colored} == {"P2.CATPart"}

    # Export CSV : nouvel en-tete.
    csv = client.get(f"/api/v1/identification/{run_id}/export.csv")
    header = csv.text.splitlines()[0]
    for col in ("replaced", "old_pn", "new_pn", "color_ref", "materials"):
        assert col in header


def test_compare_nomenclatures(client, tmp_path):
    _set_input_root(client, str(tmp_path))

    def _make(name, rows):
        # BOM a plat : le PN d'une version est son CATPart, la revision est l'indice.
        wb = Workbook()
        ws = wb.active
        ws.append(["CATPart", "SIN", "Version"])
        for r in rows:
            ws.append(r)
        p = tmp_path / name
        wb.save(p)
        return client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()["id"]

    # V0 : SIN-001 (P1, A), SIN-002 (P2, A, supprime), SIN-004 (P4, A).
    # V1 : SIN-001 (P1B, B -> PN change), SIN-003 (P3, ajoute), SIN-004 (P4, B -> indice change).
    run_a = _make(
        "v0.xlsx",
        [["P1.CATPart", "SIN-001", "A"], ["P2.CATPart", "SIN-002", "A"], ["P4.CATPart", "SIN-004", "A"]],
    )
    run_b = _make(
        "v1.xlsx",
        [["P1B.CATPart", "SIN-001", "B"], ["P3.CATPart", "SIN-003", "A"], ["P4.CATPart", "SIN-004", "B"]],
    )

    r = client.post("/api/v1/identification/compare", json={"base_run_id": run_a, "other_run_id": run_b})
    assert r.status_code == 200, r.text
    body = r.json()
    assert {e["sin"] for e in body["added_sin"]} == {"SIN-003"}
    assert {e["sin"] for e in body["removed_sin"]} == {"SIN-002"}
    assert body["added_sin"][0]["old_pn_v2"] == "P3.CATPart"
    assert body["removed_sin"][0]["old_pn"] == "P2.CATPart"
    assert body["removed_sin"][0]["old_pn_v2"] == ""
    changed = {e["sin"]: e for e in body["changed_pn"]}
    # Seul un changement de PN est reporte (SIN-001). SIN-004 garde le meme PN
    # (seule la revision change) -> non reporte par la comparaison.
    assert set(changed) == {"SIN-001"}
    # OLD P/N de V0 et V1 sont exposes ; les revisions restent exclues.
    assert changed["SIN-001"]["old_pn"] == "P1.CATPart"
    assert changed["SIN-001"]["old_pn_v2"] == "P1B.CATPart"
    assert "old_rev" not in changed["SIN-001"]

    csv = client.get(
        "/api/v1/identification/compare/export.csv",
        params={"base_run_id": run_a, "other_run_id": run_b},
    )
    assert csv.status_code == 200
    assert csv.text.splitlines()[0] == "type;sin;old_pn;old_pn_v2;designation"
    assert "new_pn" not in csv.text
    assert "SIN-003" in csv.text and "SIN-002" in csv.text
    assert "modifie" in csv.text


def test_compare_multiple_nomenclatures_preserves_pairwise_results(client, tmp_path):
    _set_input_root(client, str(tmp_path))

    def _make(name, rows):
        wb = Workbook()
        ws = wb.active
        ws.append(["CATPart", "SIN"])
        for row in rows:
            ws.append(row)
        path = tmp_path / name
        wb.save(path)
        response = client.post(
            "/api/v1/identification/nomenclature",
            json={"scope": "input", "path": str(path)},
        )
        return response.json()["id"]

    v0 = _make("multi-v0.xlsx", [["P1.CATPart", "SIN-001"]])
    v1 = _make("multi-v1.xlsx", [["P1B.CATPart", "SIN-001"], ["P2.CATPart", "SIN-002"]])
    v2 = _make("multi-v2.xlsx", [["P1B.CATPart", "SIN-001"], ["P3.CATPart", "SIN-003"]])

    chronology = client.post(
        "/api/v1/identification/compare/multi",
        json={"run_ids": [v0, v1, v2], "mode": "chronology"},
    )
    assert chronology.status_code == 200, chronology.text
    body = chronology.json()
    assert [(row["base_run_id"], row["other_run_id"]) for row in body["comparisons"]] == [
        (v0, v1),
        (v1, v2),
    ]
    pair = client.post(
        "/api/v1/identification/compare",
        json={"base_run_id": v0, "other_run_id": v1},
    ).json()
    assert body["comparisons"][0] == pair
    matrix = {row["sin"]: row for row in body["matrix"]}
    assert len(matrix["SIN-001"]["cells"]) == 3
    assert [cell["pn"] for cell in matrix["SIN-001"]["cells"]] == [
        "P1.CATPart",
        "P1B.CATPart",
        "P1B.CATPart",
    ]
    assert matrix["SIN-002"]["cells"][1]["state"] == "added"
    assert matrix["SIN-002"]["cells"][2]["state"] == "removed"
    assert matrix["SIN-003"]["cells"][2]["state"] == "added"

    reference = client.post(
        "/api/v1/identification/compare/multi",
        json={"run_ids": [v0, v1, v2], "mode": "reference", "reference_run_id": v1},
    )
    assert reference.status_code == 200, reference.text
    assert [
        (row["base_run_id"], row["other_run_id"])
        for row in reference.json()["comparisons"]
    ] == [(v1, v0), (v1, v2)]


def test_compare_old_pn_columns_only(client, tmp_path):
    """Seul un changement d'OLD P/N compte, et les deux versions sont exposees."""
    _set_input_root(client, str(tmp_path))

    def _make(name, rows):
        wb = Workbook()
        ws = wb.active
        ws.append(["SIN", "OLD P/N", "NEW P/N"])
        for r in rows:
            ws.append(r)
        p = tmp_path / name
        wb.save(p)
        return client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()["id"]

    # V0 -> V1 :
    #  SIN-001 : OLD A1->A2 (OLD change)         => modifie
    #  SIN-002 : OLD B1 inchange, NEW B1->B2     => ignore
    #  SIN-003 : inchange                        => non
    run_a = _make("v0.xlsx", [["SIN-001", "A1", "AN1"], ["SIN-002", "B1", "B1"], ["SIN-003", "C1", "C1"]])
    run_b = _make("v1.xlsx", [["SIN-001", "A2", "AN2"], ["SIN-002", "B1", "B2"], ["SIN-003", "C1", "C1"]])

    body = client.post(
        "/api/v1/identification/compare", json={"base_run_id": run_a, "other_run_id": run_b}
    ).json()
    changed = {e["sin"]: e for e in body["changed_pn"]}
    assert set(changed) == {"SIN-001"}
    # OLD P/N de V0 et V1 reportes, sans utiliser NEW P/N.
    assert changed["SIN-001"]["old_pn"] == "A1"
    assert changed["SIN-001"]["old_pn_v2"] == "A2"
    assert "new_pn" not in changed["SIN-001"]

    multi = client.post(
        "/api/v1/identification/compare/multi",
        json={"run_ids": [run_a, run_b], "mode": "chronology"},
    )
    assert multi.status_code == 200, multi.text
    matrix = {row["sin"]: row for row in multi.json()["matrix"]}
    assert [cell["pn"] for cell in matrix["SIN-001"]["cells"]] == ["A1", "A2"]
    assert matrix["SIN-002"]["cells"][1]["state"] == "unchanged"

    same = client.post(
        "/api/v1/identification/compare", json={"base_run_id": run_a, "other_run_id": run_a}
    )
    assert same.status_code == 400
    assert same.json()["code"] == "COMPARE_SAME_RUN"


def test_mono_body_from_materiaux_sheet(client, tmp_path):
    """Etape Mono-Corps : onglet Materiaux separe (identite + n colonnes slots),
    n quelconque, apparie aux pieces par CATPart."""
    _set_input_root(client, str(tmp_path))
    wb = Workbook()
    # Onglet 1 : nomenclature (identite CATPart / SIN).
    ws = wb.active
    ws.title = "Nomenclature"
    ws.append(["CATPart", "SIN", "OLD P/N"])
    for cat, sin in [("P1.CATPart", "SIN-001"), ("P2.CATPart", "SIN-002"),
                     ("P3.CATPart", "SIN-003"), ("P4.CATPart", "SIN-004")]:
        ws.append([cat, sin, f"OLD-{sin}"])
    # Onglet 2 : Materiaux (CATPart + 4 colonnes Slot).
    mat = wb.create_sheet("Materiaux")
    mat.append(["CATPart", "Slot 1", "Slot 2", "Slot 3", "Slot 4"])
    mat.append(["P1.CATPart", "A", "", "", ""])       # 1 slot -> mono
    mat.append(["P2.CATPart", "A", "A", "A", "A"])    # 4 slots identiques -> mono
    mat.append(["P3.CATPart", "A", "B", "", ""])      # distincts -> non
    mat.append(["P4.CATPart", "", "", "", ""])        # aucun slot -> non
    p = tmp_path / "nomen_mono.xlsx"
    wb.save(p)

    run_id = client.post(
        "/api/v1/identification/nomenclature",
        json={"scope": "input", "path": str(p), "sheet": "Nomenclature"},
    ).json()["id"]

    # Avant l'etape mono-corps : aucun mono_body.
    assert client.get(f"/api/v1/identification/{run_id}").json()["summary"]["mono_body"] == 0

    # Analyse autonome SANS run : renvoie le contenu (items + slots + mono_body).
    solo = client.post(
        "/api/v1/identification/mono-corps",
        json={
            "scope": "input", "path": str(p), "sheet": "Materiaux", "header_row": 1,
            "identity_field": "catpart", "identity_col": 0, "slot_cols": [1, 2, 3, 4],
        },
    )
    assert solo.status_code == 200, solo.text
    sbody = solo.json()
    assert sbody["summary"]["mono"] == 2 and sbody["summary"]["applied"] is False
    by_id = {i["identity"]: i for i in sbody["items"]}
    assert by_id["P1.CATPart"]["mono_body"] is True and by_id["P3.CATPart"]["mono_body"] is False
    assert by_id["P2.CATPart"]["slots"] == ["A", "A", "A", "A"]

    # Meme etape AVEC run_id : applique mono_body aux pieces.
    r = client.post(
        "/api/v1/identification/mono-corps",
        json={
            "scope": "input", "path": str(p), "sheet": "Materiaux", "header_row": 1,
            "identity_field": "catpart", "identity_col": 0, "slot_cols": [1, 2, 3, 4],
            "run_id": run_id,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["applied"] is True and r.json()["summary"]["mono"] == 2
    response_items = {item["identity"]: item for item in r.json()["items"]}
    assert response_items["P1.CATPart"]["old_pn"] == "OLD-SIN-001"
    assert response_items["P1.CATPart"]["mono_texture"] == "A"
    assert response_items["P2.CATPart"]["mono_texture"] == "A"
    assert response_items["P3.CATPart"]["mono_texture"] == ""
    assert client.get(f"/api/v1/identification/{run_id}").json()["summary"]["mono_body"] == 2

    mono = client.get(f"/api/v1/identification/{run_id}/items", params={"mono_body": True}).json()
    assert {i["catpart"] for i in mono} == {"P1.CATPart", "P2.CATPart"}

    # Export CSV filtre mono-corps.
    csv = client.get(f"/api/v1/identification/{run_id}/export.csv", params={"mono_body": True})
    assert "mono_body" in csv.text.splitlines()[0]
    assert "P1.CATPart" in csv.text and "P3.CATPart" not in csv.text

    # slot_cols OMIS : toutes les colonnes sauf l'identite sont comparees.
    auto = client.post(
        "/api/v1/identification/mono-corps",
        json={
            "scope": "input", "path": str(p), "sheet": "Materiaux", "header_row": 1,
            "identity_field": "catpart", "identity_col": 0,
        },
    )
    assert auto.status_code == 200, auto.text
    abody = auto.json()
    # Colonnes 1..4 (toutes sauf l'identite en 0) => meme resultat que le mapping explicite.
    assert abody["summary"]["slot_cols"] == [1, 2, 3, 4]
    assert abody["summary"]["mono"] == 2
    auto_by_id = {i["identity"]: i for i in abody["items"]}
    assert auto_by_id["P2.CATPart"]["slots"] == ["A", "A", "A", "A"]
    assert auto_by_id["P3.CATPart"]["mono_body"] is False

    # first_slot_col : 1re colonne Slot = 2 -> slots des colonnes 2..fin (col 1 ignoree).
    fs = client.post(
        "/api/v1/identification/mono-corps",
        json={
            "scope": "input", "path": str(p), "sheet": "Materiaux", "header_row": 1,
            "identity_field": "catpart", "identity_col": 0, "first_slot_col": 2,
        },
    )
    assert fs.status_code == 200, fs.text
    assert fs.json()["summary"]["slot_cols"] == [2, 3, 4]
    fs_by_id = {i["identity"]: i for i in fs.json()["items"]}
    assert fs_by_id["P2.CATPart"]["slots"] == ["A", "A", "A"]
