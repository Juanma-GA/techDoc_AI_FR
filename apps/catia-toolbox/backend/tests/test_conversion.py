"""Tests route /api/v1 conversion CATIA 3D -> Composer."""

from __future__ import annotations


def _scan(client, path: str) -> str:
    r = client.post("/api/v1/imports/scan", json={"path": path})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_conversion_plan(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    r = client.post(f"/api/v1/imports/{imp_id}/conversion", json={})
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]
    assert r.json()["summary"]["total"] >= 1

    items = client.get(f"/api/v1/conversions/{run_id}/items").json()
    assert items
    # Sortie a plat en SMGXML dans un dossier auto '<...>_Converti'.
    assert all(it["target_path"].endswith(".smgxml") for it in items)
    assert all("_Converti/" in it["target_path"] for it in items)
    # A plat : pas de sous-dossier sous le dossier de sortie.
    assert all(it["target_path"].count("/") == 1 for it in items)

    csv = client.get(f"/api/v1/conversions/{run_id}/export.csv")
    assert csv.status_code == 200
    assert csv.text.splitlines()[0] == "source_path;target_path;source_ext"

    script = client.get(f"/api/v1/conversions/{run_id}/export.script")
    assert script.status_code == 200
    assert "text/x-python" in script.headers["content-type"]
    body = script.text
    assert "win32com" in body
    assert "DRY_RUN = True" in body
    assert "PLAN = [" in body
    # le plan embarque doit referencer une cible .smgxml + le nettoyage de sortie
    assert ".smgxml" in body
    assert "tidy_output_dir" in body
    # Posture non destructive : le script deplace, ne supprime pas.
    assert "os.remove" not in body
    assert "_autres" in body


def test_conversion_lists_all_files(client, synthetic_tree) -> None:
    """Tous les fichiers sont listes ; CAO pre-selectionnee, le reste deselectionne."""
    imp_id = _scan(client, str(synthetic_tree))
    run_id = client.post(f"/api/v1/imports/{imp_id}/conversion", json={}).json()["id"]
    items = client.get(f"/api/v1/conversions/{run_id}/items").json()
    by_ext = {}
    for it in items:
        by_ext.setdefault(it["source_ext"], set()).add(it["status"])
    # Un CATPart (CAO) est accepte par defaut ; un .txt (anomalie) est rejete.
    assert "catpart" in by_ext and by_ext["catpart"] == {"accepted"}
    assert "txt" in by_ext and by_ext["txt"] == {"rejected"}


def test_conversion_execute_dry_run(client, synthetic_tree) -> None:
    """L'app peut lancer le script en dry-run (aucun appel Composer)."""
    imp_id = _scan(client, str(synthetic_tree))
    run_id = client.post(f"/api/v1/imports/{imp_id}/conversion", json={}).json()["id"]

    r = client.post(f"/api/v1/conversions/{run_id}/execute", json={"dry_run": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is True
    assert body["returncode"] == 0
    assert "DRY_RUN=True" in body["stdout"]

    # Execution reelle sans confirmation -> refus (garde-fou).
    ko = client.post(f"/api/v1/conversions/{run_id}/execute", json={"dry_run": False, "confirm": False})
    assert ko.status_code == 400
    assert ko.json()["code"] == "EXEC_CONFIRM_REQUIRED"


def test_conversion_license_server_injected(client, synthetic_tree) -> None:
    """Le serveur de licence Composer configure est embarque dans le script."""
    r = client.post("/api/v1/settings", json={"composer_license_server": "4085@srv-lic"})
    assert r.status_code == 200, r.text
    assert r.json()["composer_license_server"] == "4085@srv-lic"

    imp_id = _scan(client, str(synthetic_tree))
    run_id = client.post(f"/api/v1/imports/{imp_id}/conversion", json={}).json()["id"]
    body = client.get(f"/api/v1/conversions/{run_id}/export.script").text
    assert "COMPOSER_LICENSE_SERVER" in body
    assert '"4085@srv-lic"' in body
    assert "apply_license" in body


def test_conversion_deselect(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    run_id = client.post(f"/api/v1/imports/{imp_id}/conversion", json={}).json()["id"]
    items = client.get(f"/api/v1/conversions/{run_id}/items").json()
    assert items
    first = items[0]["id"]

    # Deselection d'un item -> status rejected.
    r = client.patch(f"/api/v1/conversions/{run_id}/items/{first}", json={"status": "rejected"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"

    # Le script ne doit plus referencer la source deselectionnee.
    rejected_src = items[0]["source_path"]
    body = client.get(f"/api/v1/conversions/{run_id}/export.script").text
    assert rejected_src not in body

    # Re-selection en lot.
    rb = client.post(
        f"/api/v1/conversions/{run_id}/items/bulk-status",
        json={"item_ids": [first], "status": "accepted"},
    )
    assert rb.status_code == 200, rb.text
    assert any(it["id"] == first and it["status"] == "accepted" for it in rb.json())
