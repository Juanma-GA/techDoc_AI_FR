"""Tests route /api/v1/diff (comparaison de deux imports)."""

from __future__ import annotations


def _scan(client, path: str) -> str:
    r = client.post("/api/v1/imports/scan", json={"path": path})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_diff_detects_changes(client, synthetic_tree) -> None:
    base_id = _scan(client, str(synthetic_tree))

    # Mutation de l'arborescence : modif (taille), ajout, suppression.
    (synthetic_tree / "MAJUSCULE.STP").write_text("plus de contenu qu'avant", encoding="utf-8")
    (synthetic_tree / "exports" / "NOUVELLE.CATPart").write_text("x", encoding="utf-8")
    (synthetic_tree / "BREL" / "support.stp").unlink()

    other_id = _scan(client, str(synthetic_tree))

    r = client.post("/api/v1/diff", json={"base_import_id": base_id, "other_import_id": other_id})
    assert r.status_code == 200, r.text
    summary = r.json()["summary"]
    assert summary["added"] >= 1
    assert summary["removed"] >= 1
    assert summary["modified"] >= 1

    run_id = r.json()["id"]
    entries = client.get(f"/api/v1/diff/{run_id}/entries").json()
    assert any(e["change_type"] == "added" for e in entries)

    csv = client.get(f"/api/v1/diff/{run_id}/export.csv")
    assert csv.status_code == 200
    assert csv.text.splitlines()[0] == "rel_path;change_type;detail"


def test_diff_import_404(client, synthetic_tree) -> None:
    base_id = _scan(client, str(synthetic_tree))
    r = client.post(
        "/api/v1/diff",
        json={"base_import_id": base_id, "other_import_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404
