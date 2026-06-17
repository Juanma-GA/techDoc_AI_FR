"""Tests route /api/v1 remplacement de pieces."""

from __future__ import annotations

import io


def _scan(client, path: str) -> str:
    r = client.post("/api/v1/imports/scan", json={"path": path})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_replacement_plan(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    mapping = b"old;new\nPIECE_001.CATPart;PIECE_NEW.CATPart\n"
    r = client.post(
        f"/api/v1/imports/{imp_id}/replacement",
        files={"file": ("map.csv", io.BytesIO(mapping), "text/csv")},
    )
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]
    # PIECE_001.CATPart apparait 2 fois dans l'arbo factice.
    assert r.json()["summary"]["total"] >= 2

    items = client.get(f"/api/v1/replacements/{run_id}/items").json()
    assert all(it["new_ref"] == "PIECE_NEW.CATPart" for it in items)

    csv = client.get(f"/api/v1/replacements/{run_id}/export.csv")
    assert csv.status_code == 200
    assert csv.text.splitlines()[0] == "occurrence_path;old_ref;new_ref"

    macro = client.get(f"/api/v1/replacements/{run_id}/export.macro")
    assert macro.status_code == 200
    assert "CATMain" in macro.text


def test_replacement_from_source(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    # Le mapping vit dans la Source ; on le choisit par chemin (pas d'upload).
    mapping = synthetic_tree / "mapping.csv"
    mapping.write_text("old;new\nPIECE_001.CATPart;PIECE_NEW.CATPart\n", encoding="utf-8")
    assert client.post("/api/v1/settings", json={"onedrive_input_root": str(synthetic_tree)}).status_code == 200
    r = client.post(
        f"/api/v1/imports/{imp_id}/replacement/source",
        json={"scope": "input", "path": str(mapping)},
    )
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["total"] >= 2


def test_replacement_from_source_rejects_outside_root(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    (synthetic_tree / "sub").mkdir(exist_ok=True)
    assert client.post("/api/v1/settings", json={"onedrive_input_root": str(synthetic_tree / "sub")}).status_code == 200
    (synthetic_tree / "m.csv").write_text("old;new\na;b\n", encoding="utf-8")
    r = client.post(
        f"/api/v1/imports/{imp_id}/replacement/source",
        json={"scope": "input", "path": str(synthetic_tree / "m.csv")},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "PATH_OUTSIDE_ROOT"


def test_replacement_empty_mapping(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    r = client.post(
        f"/api/v1/imports/{imp_id}/replacement",
        files={"file": ("map.csv", io.BytesIO(b"old;new\n"), "text/csv")},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "MAPPING_EMPTY"
