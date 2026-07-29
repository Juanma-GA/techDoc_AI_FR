"""Tests Etapes 3 & 4 - SMGXML recolor / rename (fixtures synthetiques)."""

from __future__ import annotations

from pathlib import Path

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


def test_tree(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    smg = _make_smgxml(tmp_path)
    r = client.post("/api/v1/smgxml/tree", json={"scope": "input", "path": str(smg)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["root_label"] == "engine.smgxml"
    # 1 racine <Document> + 4 enfants = 5 noeuds.
    assert body["node_count"] == 5
    root = body["nodes"][0]
    assert root["name"] == "Document" and root["kind"] == "folder"
    child_names = [c["name"] for c in root["children"]]
    # Le nom d'un acteur (attribut) est ajoute entre parentheses au tag.
    assert "Actor (SIN-001)" in child_names
    # Feuille (sans enfant) -> kind "file".
    assert all(c["kind"] == "file" for c in root["children"])


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
    """Nomenclature : NEW P/N = AA-200, Ref Couleur = Visserie, RGB 255,0,0."""
    wb = Workbook()
    ws = wb.active
    ws.append(["CATPart", "SIN", "NEW P/N", "Ref Couleur", "Couleur", "Materiaux"])
    ws.append(["P.CATPart", "SIN-001", "AA-200", "Visserie", "255,0,0", ""])
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
        "match_by": "pn", "simple_only": False,
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
        "match_by": "pn", "simple_only": False,
        "set_style": True, "set_color": False, "apply": True,
    })
    assert r.status_code == 200, r.text
    written = smg.read_text(encoding="utf-8")
    # Balise <ActorStyle> reconnue + valeur = <bibliotheque>\<nom>.SMGStyleSet.
    assert "C:\\Tex\\Lib\\Visserie.SMGStyleSet" in written


def _make_batch_nomen(client, tmp_path):
    """Nomenclature avec 1 piece remplacee : SIN 030A5, OLD 2469M86P01 -> NEW 2568M87P02."""
    wb = Workbook()
    ws = wb.active
    ws.append(["SIN", "OLD P/N", "NEW P/N"])
    ws.append(["030A5", "2469M86P01", "2568M87P02"])
    p = tmp_path / "nomen_batch.xlsx"
    wb.save(p)
    return client.post("/api/v1/identification/nomenclature", json={"scope": "input", "path": str(p)}).json()["id"]


def _make_batch_tree(tmp_path):
    """Arborescence COMPOSER (COMP PROD / COMP PART) + dossier converties."""
    composer = tmp_path / "COMPOSER u495"
    prod = composer / "COMP PROD"
    part = composer / "COMP PART"
    conv = tmp_path / "U600 CONVERTIES"
    for d in (prod, part, conv):
        d.mkdir(parents=True)
    # Assemblage du SIN referencant le nom de base OLD.
    (prod / "030A5_SPACER-ANTI-MIGRATION.smgXml").write_text(
        '<Document><Ref name="GE_030A5_2469M86P01_P_01" />'
        '<Geom src="GE_030A5_2469M86P01_P_01.smgGeom" /></Document>',
        encoding="utf-8",
    )
    # Fichiers pieces OLD (COMP PART).
    (part / "GE_030A5_2469M86P01_P_01.smgXml").write_text("<old/>", encoding="utf-8")
    (part / "GE_030A5_2469M86P01_P_01.smgGeom").write_text("geom", encoding="utf-8")
    # Fichiers pieces NEW (converties).
    (conv / "GE_030A5_2568M87P02_X000_001.smgXml").write_text("<new/>", encoding="utf-8")
    (conv / "GE_030A5_2568M87P02_X000_001.smgGeom").write_text("geomnew", encoding="utf-8")
    return composer, conv, prod, part


def test_batch_rename_dryrun_then_apply(client, tmp_path):
    _set_input_root(client, str(tmp_path))
    run_id = _make_batch_nomen(client, tmp_path)
    composer, conv, prod, part = _make_batch_tree(tmp_path)

    body = {
        "scope": "input",
        "composer_root": str(composer),
        "converted_root": str(conv),
        "nomenclature_run_id": run_id,
    }

    # 1. Dry-run : rien ecrit, statut ok, references comptees.
    dry = client.post("/api/v1/smgxml/batch-rename", json=body)
    assert dry.status_code == 200, dry.text
    d = dry.json()
    assert d["summary"]["total"] == 1 and d["summary"]["ok"] == 1 and d["summary"]["applied"] == 0
    it = d["items"][0]
    assert it["status"] == "ok"
    assert it["old_stem"] == "GE_030A5_2469M86P01_P_01"
    assert it["new_stem"] == "GE_030A5_2568M87P02_X000_001"
    assert it["replacements"] == 2  # <Ref name> + <Geom src>
    # OLD toujours en place apres dry-run.
    assert (part / "GE_030A5_2469M86P01_P_01.smgXml").exists()

    # 2. Apply : archive OLD, copie NEW, Ctrl+H dans l'assemblage (+ .bak).
    body["apply"] = True
    applied = client.post("/api/v1/smgxml/batch-rename", json=body)
    assert applied.status_code == 200, applied.text
    a = applied.json()["items"][0]
    assert a["applied"] is True

    # OLD archives (plus a la racine COMP PART), NEW copies.
    assert not (part / "GE_030A5_2469M86P01_P_01.smgXml").exists()
    archive = next(part.glob("ARCHIVE_*"))
    assert (archive / "GE_030A5_2469M86P01_P_01.smgXml").exists()
    assert (archive / "GE_030A5_2469M86P01_P_01.smgGeom").exists()
    assert (part / "GE_030A5_2568M87P02_X000_001.smgXml").exists()
    assert (part / "GE_030A5_2568M87P02_X000_001.smgGeom").exists()

    # Assemblage : references remplacees + .bak conserve.
    asm = prod / "030A5_SPACER-ANTI-MIGRATION.smgXml"
    txt = asm.read_text(encoding="utf-8")
    assert "GE_030A5_2469M86P01_P_01" not in txt
    assert txt.count("GE_030A5_2568M87P02_X000_001") == 2
    assert (prod / "030A5_SPACER-ANTI-MIGRATION.smgXml.bak").exists()


def test_batch_rename_missing_new(client, tmp_path):
    """NEW introuvable dans le dossier converties -> statut new_not_found, ignore."""
    _set_input_root(client, str(tmp_path))
    run_id = _make_batch_nomen(client, tmp_path)
    composer, conv, _prod, part = _make_batch_tree(tmp_path)
    # Supprime les fichiers NEW.
    for f in conv.glob("*"):
        f.unlink()

    r = client.post("/api/v1/smgxml/batch-rename", json={
        "scope": "input", "composer_root": str(composer),
        "converted_root": str(conv), "nomenclature_run_id": run_id, "apply": True,
    })
    assert r.status_code == 200, r.text
    it = r.json()["items"][0]
    assert it["status"] == "new_not_found" and it["applied"] is False
    # OLD non touche (aucune ecriture sur item non ok).
    assert (part / "GE_030A5_2469M86P01_P_01.smgXml").exists()
