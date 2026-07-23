"""Tests Etapes 3 & 4 - SMGXML recolor / rename (fixtures synthetiques)."""

from __future__ import annotations

from openpyxl import Workbook


def _set_input_root(client, root: str) -> None:
    assert client.post("/api/v1/settings", json={"onedrive_input_root": root}).status_code == 200


def _make_smgxml(tmp_path):
    content = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<Document>\n"
        '  <Actor name="SIN-001" color="" />\n'
        '  <Actor name="SIN-002" color="0,0,0" />\n'
        '  <Reference actorName="OLD_PIECE" />\n'
        '  <Actor name="OLD_PIECE" color="" />\n'
        "</Document>\n"
    )
    p = tmp_path / "engine.smgxml"
    p.write_text(content, encoding="utf-8")
    return p


def _make_nomenclature(client, tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["CATPart", "SIN", "Couleur"])
    ws.append(["PIECE_001.CATPart", "SIN-001", "255,0,0"])
    ws.append(["PIECE_002.CATPart", "SIN-002", ""])
    p = tmp_path / "nomen.xlsx"
    wb.save(p)
    return client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()["id"]


def test_inspect(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml(tmp_path)
    r = client.post("/api/v1/smgxml/inspect", json={"scope": "input", "path": str(smg)})
    assert r.status_code == 200, r.text
    names = {a["name"] for a in r.json()}
    assert {"SIN-001", "SIN-002", "OLD_PIECE"} <= names


def test_recolor_dryrun_then_apply(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml(tmp_path)
    nom_id = _make_nomenclature(client, tmp_path)

    # Dry-run : 1 changement (SIN-001 vide -> 255,0,0), rien ecrit.
    r = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id, "match_by": "sin", "apply": False,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["changes"] == 1
    assert body["applied"] is False
    assert "255,0,0" not in smg.read_text(encoding="utf-8")  # rien ecrit

    # Apply : ecrit le fichier + cree un .bak.
    r2 = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id, "match_by": "sin", "apply": True,
    })
    assert r2.status_code == 200, r2.text
    assert r2.json()["applied"] is True
    assert "255,0,0" in smg.read_text(encoding="utf-8")
    assert (tmp_path / "engine.smgxml.bak").exists()


def test_rename_dryrun(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml(tmp_path)
    r = client.post("/api/v1/smgxml/rename", json={
        "scope": "input", "path": str(smg),
        "mapping": [{"old": "OLD_PIECE", "new": "NEW_PIECE"}],
        "apply": False,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    # 2 occurrences : Reference@actorName + Actor@name.
    assert body["summary"]["changes"] == 2
    assert body["applied"] is False
    run_id = body["id"]
    changes = client.get(f"/api/v1/smgxml/{run_id}/changes").json()
    assert all(c["new_value"] == "NEW_PIECE" for c in changes)


def _make_smgxml_composer(tmp_path):
    """SMGXML au format Composer : Actor.Style @Value + SCLIT>Neutral>Actor.Color."""
    content = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<Document>\n"
        '  <Actor name="AA-200">\n'
        '    <Actor.Style Value="Defaut" />\n'
        "    <SCLIT><Neutral>\n"
        '      <Actor.Color color="" />\n'
        "    </Neutral></SCLIT>\n"
        "  </Actor>\n"
        "</Document>\n"
    )
    p = tmp_path / "composer.smgxml"
    p.write_text(content, encoding="utf-8")
    return p


def _make_nomenclature_full(client, tmp_path):
    """Nomenclature : NEW P/N = AA-200, Ref Couleur = Visserie, RGB 255,0,0,
    un seul slot renseigne => piece mono-corps (ciblee par simple_only)."""
    wb = Workbook()
    ws = wb.active
    ws.append(["CATPart", "SIN", "NEW P/N", "Ref Couleur", "Couleur", "Materiaux", "Slot 1"])
    ws.append(["P.CATPart", "SIN-001", "AA-200", "Visserie", "255,0,0", "", "S1"])
    p = tmp_path / "nomen_full.xlsx"
    wb.save(p)
    return client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()["id"]


def test_recolor_style_and_color_by_pn(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml_composer(tmp_path)
    nom_id = _make_nomenclature_full(client, tmp_path)

    # match_by=pn : cible l'acteur AA-200 ; pose le style (Visserie) ET la couleur.
    r = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id,
        "match_by": "pn", "simple_only": True,
        "set_style": True, "set_color": True, "apply": True,
    })
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]
    types = {c["change_type"] for c in client.get(f"/api/v1/smgxml/{run_id}/changes").json()}
    assert {"style", "color"} <= types
    written = smg.read_text(encoding="utf-8")
    # Extension de style .SMGStyleSet appliquee par defaut (config textures).
    assert "Visserie.SMGStyleSet" in written
    assert "255,0,0" in written


def test_recolor_style_only(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml_composer(tmp_path)
    nom_id = _make_nomenclature_full(client, tmp_path)
    r = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id,
        "match_by": "pn", "set_style": True, "set_color": False, "apply": False,
    })
    assert r.status_code == 200, r.text
    changes = client.get(f"/api/v1/smgxml/{r.json()['id']}/changes").json()
    assert all(c["change_type"] == "style" for c in changes)
    assert changes  # au moins le style


def test_recolor_uses_referential(client, tmp_path):
    """Ref Couleur (ex. 'Visserie') -> RGB via le referentiel, ecrit dans Actor.Color."""
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml_composer(tmp_path)  # acteur AA-200 avec Actor.Color

    # Referentiel : Visserie = (10, 20, 30).
    ref = client.post("/api/v1/colorref", json={"entries": [{"name": "Visserie", "r": 10, "g": 20, "b": 30}]})
    assert ref.status_code == 200, ref.text
    assert client.get("/api/v1/colorref").json()["entries"][0]["name"] == "Visserie"

    # Nomenclature : Ref Couleur = Visserie, PAS de colonne Couleur.
    wb = Workbook()
    ws = wb.active
    ws.append(["CATPart", "NEW P/N", "Ref Couleur", "Materiaux"])
    ws.append(["P.CATPart", "AA-200", "Visserie", ""])
    p = tmp_path / "nomen_ref.xlsx"
    wb.save(p)
    nom_id = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()["id"]

    r = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id,
        "match_by": "pn", "set_style": False, "set_color": True, "apply": True,
    })
    assert r.status_code == 200, r.text
    types = {c["change_type"] for c in client.get(f"/api/v1/smgxml/{r.json()['id']}/changes").json()}
    assert "color" in types
    assert "10,20,30" in smg.read_text(encoding="utf-8")


def test_recolor_no_mono(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml(tmp_path)
    wb = Workbook()
    ws = wb.active
    ws.append(["CATPart", "SIN", "Couleur"])
    ws.append(["P.CATPart", "SIN-009", ""])  # pas de couleur
    p = tmp_path / "nomono.xlsx"
    wb.save(p)
    nom_id = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()["id"]
    r = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id, "apply": False,
    })
    assert r.status_code == 400
    assert r.json()["code"] == "NO_COLOR_TARGET"


def test_recolor_simple_only_without_slots(client, tmp_path):
    """'mono-corps seulement' sans colonnes Slot mappees -> erreur explicite."""
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml_composer(tmp_path)
    wb = Workbook()
    ws = wb.active
    ws.append(["CATPart", "NEW P/N", "Ref Couleur"])  # pas de colonne Slot
    ws.append(["P.CATPart", "AA-200", "Visserie"])
    p = tmp_path / "noslots.xlsx"
    wb.save(p)
    nom_id = client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()["id"]
    r = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id,
        "match_by": "pn", "simple_only": True, "set_style": True, "set_color": False, "apply": False,
    })
    assert r.status_code == 400
    assert r.json()["code"] == "NO_MONO_BODY"


def _make_smgxml_actorstyle(tmp_path):
    """Variante Composer : balise <ActorStyle> (sans point)."""
    content = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<Document>\n"
        '  <Actor name="AA-200">\n'
        '    <ActorStyle Value="Defaut" />\n'
        "  </Actor>\n"
        "</Document>\n"
    )
    p = tmp_path / "actorstyle.smgxml"
    p.write_text(content, encoding="utf-8")
    return p


def test_texture_config_library_and_ext(client, tmp_path):
    """Config textures : le nom de style ecrit dans le SMGXML est prefixe par la
    bibliotheque et suffixe par l'extension (.SMGStyleSet). Balise ActorStyle."""
    _set_input_root(client, str(tmp_path))

    # Config textures : bibliotheque + extension personnalisee.
    cfg = client.post("/api/v1/colorref/texture", json={"library": "C:\\Tex\\Lib", "ext": ".SMGStyleSet"})
    assert cfg.status_code == 200, cfg.text
    assert client.get("/api/v1/colorref/texture").json()["library"] == "C:\\Tex\\Lib"

    smg = _make_smgxml_actorstyle(tmp_path)
    nom_id = _make_nomenclature_full(client, tmp_path)  # Ref Couleur = Visserie, mono-corps

    r = client.post("/api/v1/smgxml/recolor", json={
        "scope": "input", "path": str(smg), "nomenclature_run_id": nom_id,
        "match_by": "pn", "simple_only": True,
        "set_style": True, "set_color": False, "apply": True,
    })
    assert r.status_code == 200, r.text
    written = smg.read_text(encoding="utf-8")
    # Balise <ActorStyle> reconnue + valeur = <bibliotheque>\<nom>.SMGStyleSet.
    assert "C:\\Tex\\Lib\\Visserie.SMGStyleSet" in written
