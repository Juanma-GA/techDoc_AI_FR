from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.db.models import AppConfig, NomenclatureItem, NomenclatureRun
from app.db.session import SessionLocal


def test_stats_only_counts_active_modules(client) -> None:
    response = client.get("/api/v1/admin/stats")
    assert response.status_code == 200
    assert set(response.json()) == {
        "imports", "nodes", "diffs", "conversions", "colorizations",
        "nomenclatures", "smgxml_runs", "total_size_bytes",
    }


def test_reset_all_deletes_database_and_local_uploads_but_preserves_config(
    client, tmp_path, monkeypatch
) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setattr(settings, "storage_dir", str(storage_root))

    local_upload = storage_root / "local" / "upload-1" / "nomenclature.xlsx"
    local_upload.parent.mkdir(parents=True)
    local_upload.write_bytes(b"temporary user upload")

    with SessionLocal() as db:
        run = NomenclatureRun(source_ref="nomenclature.xlsx", sheet="Nomenclature")
        db.add(run)
        db.flush()
        run_id = run.id
        db.add(NomenclatureItem(run_id=run.id, sin="SIN-001", mono_body=True))
        db.add(AppConfig(key="reset-test-config", value="preserved"))
        db.commit()

    response = client.post("/api/v1/admin/reset/all")

    assert response.status_code == 200, response.text
    deleted = response.json()["deleted"]
    assert deleted["nomenclature_runs"] == 1
    assert deleted["nomenclature_items"] == 1
    assert deleted["local_upload_files"] == 1
    assert not local_upload.exists()

    with SessionLocal() as db:
        assert db.get(NomenclatureRun, run_id) is None
        assert db.get(AppConfig, "reset-test-config").value == "preserved"
