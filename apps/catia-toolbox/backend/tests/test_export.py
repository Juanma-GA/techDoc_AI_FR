"""Tests routes export (CSV + script dry-run)."""

from __future__ import annotations


def _run_all_accepted(client, synthetic_tree) -> str:
    imp_id = client.post("/api/v1/imports/scan", json={"path": str(synthetic_tree)}).json()["id"]
    client.post(f"/api/v1/imports/{imp_id}/optimize", json={"use_llm": False})
    run = client.get(f"/api/v1/imports/{imp_id}/optimize/runs").json()[0]
    suggestions = client.get(f"/api/v1/runs/{run['id']}/suggestions").json()
    ids = [s["id"] for s in suggestions]
    client.post("/api/v1/suggestions/bulk-status", json={"ids": ids, "status": "accepted"})
    return run["id"]


def test_export_csv(client, synthetic_tree) -> None:
    run_id = _run_all_accepted(client, synthetic_tree)
    r = client.get(f"/api/v1/runs/{run_id}/export.csv")
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers["content-type"]
    body = r.text
    assert body.splitlines()[0] == "old_path;new_path;action;confidence;rationale"


def test_export_bat_dryrun(client, synthetic_tree) -> None:
    run_id = _run_all_accepted(client, synthetic_tree)
    r = client.get(f"/api/v1/runs/{run_id}/export.script", params={"os": "bat"})
    assert r.status_code == 200, r.text
    body = r.text
    assert "DRY-RUN" in body
    assert "mkdir" in body and "move" in body
    assert "del " not in body.lower()


def test_export_sh_dryrun(client, synthetic_tree) -> None:
    run_id = _run_all_accepted(client, synthetic_tree)
    r = client.get(f"/api/v1/runs/{run_id}/export.script", params={"os": "sh"})
    assert r.status_code == 200, r.text
    body = r.text
    assert "mkdir -p" in body and "mv " in body
    assert "rm " not in body


def test_export_invalid_os(client, synthetic_tree) -> None:
    run_id = _run_all_accepted(client, synthetic_tree)
    r = client.get(f"/api/v1/runs/{run_id}/export.script", params={"os": "exe"})
    assert r.status_code == 400
    assert r.json()["code"] == "SCRIPT_OS_INVALID"


def _set_output_root(client, root: str) -> None:
    assert client.post(
        "/api/v1/settings", json={"onedrive_output_root": root}
    ).status_code == 200


def test_export_save_writes_to_output(client, synthetic_tree, tmp_path) -> None:
    out_dir = tmp_path / "onedrive_out"
    out_dir.mkdir()
    _set_output_root(client, str(out_dir))
    run_id = _run_all_accepted(client, synthetic_tree)

    r = client.post(
        f"/api/v1/runs/{run_id}/export/save",
        json={"filename": "plan_lot3", "kind": "csv"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    written = out_dir / "plan_lot3.csv"
    assert written.exists()
    assert body["bytes_written"] == written.stat().st_size
    assert written.read_text(encoding="utf-8").splitlines()[0].startswith("old_path;")


def test_export_save_rejects_traversal(client, synthetic_tree, tmp_path) -> None:
    out_dir = tmp_path / "onedrive_out2"
    out_dir.mkdir()
    _set_output_root(client, str(out_dir))
    run_id = _run_all_accepted(client, synthetic_tree)

    r = client.post(
        f"/api/v1/runs/{run_id}/export/save",
        json={"filename": "../escape.csv", "kind": "csv"},
    )
    # safe_filename neutralise les '..' -> le fichier reste sous la racine.
    assert r.status_code == 200, r.text
    assert (tmp_path / "escape.csv").exists() is False


def test_export_save_without_output_root(client, synthetic_tree) -> None:
    run_id = _run_all_accepted(client, synthetic_tree)
    r = client.post(
        f"/api/v1/runs/{run_id}/export/save",
        json={"filename": "plan", "kind": "csv"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "ROOT_NOT_CONFIGURED"


def test_export_save_invalid_kind(client, synthetic_tree, tmp_path) -> None:
    out_dir = tmp_path / "onedrive_out3"
    out_dir.mkdir()
    _set_output_root(client, str(out_dir))
    run_id = _run_all_accepted(client, synthetic_tree)
    r = client.post(
        f"/api/v1/runs/{run_id}/export/save",
        json={"filename": "plan", "kind": "exe"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "EXPORT_KIND_INVALID"
