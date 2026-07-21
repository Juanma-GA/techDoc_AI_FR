"""Routes capitalisation : templates, projets, tables, extraction, export CSV."""

from __future__ import annotations


def _set_config(key: str, value: str) -> None:
    from app.db import models
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(models.AppConfig, key)
        if row is None:
            db.add(models.AppConfig(key=key, value=value))
        else:
            row.value = value
        db.commit()
    finally:
        db.close()


def _template(client) -> str:
    r = client.post(
        "/api/v1/templates",
        json={
            "name": "Nomenclature",
            "description": "Lignes d'articles",
            "columns": [
                {"key": "ref", "label": "Reference", "type": "text", "rule": "La reference article"},
                {"key": "qty", "label": "Quantite", "type": "number", "rule": "La quantite"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _project(client) -> str:
    r = client.post("/api/v1/projects", json={"name": "Projet A"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _project_table(client) -> str:
    tpl = _template(client)
    proj = _project(client)
    r = client.post(
        "/api/v1/project-tables",
        json={"project_id": proj, "template_id": tpl, "name": "Nomenclature A"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [c["key"] for c in body["columns"]] == ["ref", "qty"]  # snapshot colonnes
    return body["id"]


def test_template_crud(client) -> None:
    tid = _template(client)
    r = client.get("/api/v1/templates")
    assert r.status_code == 200
    assert any(t["id"] == tid for t in r.json())


def test_create_project_table_snapshots_columns(client) -> None:
    table_id = _project_table(client)
    r = client.get(f"/api/v1/project-tables/{table_id}")
    assert r.status_code == 200
    assert r.json()["row_count"] == 0


def test_extract_llm_disabled_returns_empty(client) -> None:
    from app.core.mistral_client import LLM_ENABLED_KEY

    _set_config(LLM_ENABLED_KEY, "false")
    table_id = _project_table(client)
    r = client.post(
        "/api/v1/extract",
        data={"project_table_id": table_id},
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows_added"] == 0
    assert "desactive" in body["warning"].lower()


def test_extract_persists_rows(client, monkeypatch) -> None:
    from app.core.mistral_client import MistralClient

    _set_config("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(MistralClient, "ocr", lambda self, data, **kw: "| ref | qty |\n| A1 | 2 |")
    monkeypatch.setattr(
        MistralClient,
        "chat",
        lambda self, messages, **kw: '[{"ref": "A1", "qty": "2"}, {"ref": "B2", "qty": 3}]',
    )

    table_id = _project_table(client)
    r = client.post(
        "/api/v1/extract",
        data={"project_table_id": table_id},
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_added"] == 2
    assert body["rows"][0]["values"]["ref"] == "A1"
    assert body["rows"][0]["values"]["qty"] == 2  # coerce number

    rows = client.get(f"/api/v1/project-tables/{table_id}/rows").json()
    assert len(rows) == 2


def test_export_writes_csv(client, monkeypatch, tmp_path) -> None:
    from app.core.mistral_client import MistralClient

    _set_config("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(MistralClient, "ocr", lambda self, data, **kw: "x")
    monkeypatch.setattr(MistralClient, "chat", lambda self, messages, **kw: '[{"ref": "A1", "qty": 2}]')

    table_id = _project_table(client)
    client.post(
        "/api/v1/extract",
        data={"project_table_id": table_id},
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    r = client.post(
        "/api/v1/export",
        json={"project_table_id": table_id, "target_dir": str(tmp_path)},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows"] == 1
    assert body["format"] == "csv"
    written = tmp_path / "Projet_A__Nomenclature_A.csv"
    assert written.exists()
    content = written.read_text(encoding="utf-8-sig")
    assert "Reference" in content and "A1" in content


def test_export_writes_xlsx(client, monkeypatch, tmp_path) -> None:
    from openpyxl import load_workbook

    from app.core.mistral_client import MistralClient

    _set_config("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(MistralClient, "ocr", lambda self, data, **kw: "x")
    monkeypatch.setattr(MistralClient, "chat", lambda self, messages, **kw: '[{"ref": "A1", "qty": 2}]')

    table_id = _project_table(client)
    client.post(
        "/api/v1/extract",
        data={"project_table_id": table_id},
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    r = client.post(
        "/api/v1/export",
        json={"project_table_id": table_id, "target_dir": str(tmp_path), "format": "xlsx"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["format"] == "xlsx"
    written = tmp_path / "Projet_A__Nomenclature_A.xlsx"
    assert written.exists()
    ws = load_workbook(written).active
    header = [c.value for c in ws[1]]
    assert "Reference" in header and "Quantite" in header
    assert ws.cell(row=2, column=1).value == "A1"


def test_export_invalid_target_dir(client) -> None:
    table_id = _project_table(client)
    r = client.post(
        "/api/v1/export",
        json={"project_table_id": table_id, "target_dir": "/chemin/inexistant/xyz"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "TARGET_DIR_INVALID"


def test_rename_project(client) -> None:
    pid = _project(client)
    r = client.put(f"/api/v1/projects/{pid}", json={"name": "Projet B"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Projet B"
    assert any(p["name"] == "Projet B" for p in client.get("/api/v1/projects").json())


def test_rename_project_table(client) -> None:
    table_id = _project_table(client)
    r = client.patch(f"/api/v1/project-tables/{table_id}", json={"name": "Nomenclature v2"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Nomenclature v2"
    assert client.get(f"/api/v1/project-tables/{table_id}").json()["name"] == "Nomenclature v2"


def test_rename_project_not_found(client) -> None:
    r = client.put("/api/v1/projects/does-not-exist", json={"name": "X"})
    assert r.status_code == 404
    assert r.json()["code"] == "PROJECT_NOT_FOUND"


def test_extract_and_images(client, monkeypatch, tmp_path) -> None:
    import app.api.extract as extract_mod
    from app.config import settings
    from app.core.mistral_client import MistralClient

    _set_config("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    monkeypatch.setattr(MistralClient, "ocr", lambda self, data, **kw: "x")
    monkeypatch.setattr(MistralClient, "chat", lambda self, m, **kw: '[{"ref": "A1", "qty": 1}]')

    def fake_images(pdf_bytes, out_dir, doc_id):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "img1.jpg").write_bytes(b"\xff\xd8\xff\xe0fakejpg")
        return [{"filename": "img1.jpg", "page": 1}]

    monkeypatch.setattr(extract_mod, "extract_images", fake_images)

    table_id = _project_table(client)
    r = client.post(
        "/api/v1/extract",
        data={"project_table_id": table_id},
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["images_added"] == 1

    imgs = client.get(f"/api/v1/project-tables/{table_id}/images").json()
    assert len(imgs) == 1
    image_id = imgs[0]["id"]

    served = client.get(f"/api/v1/images/{image_id}/file")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/")

    deleted = client.delete(f"/api/v1/images/{image_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/project-tables/{table_id}/images").json() == []


def test_admin_stats_counts(client) -> None:
    _project_table(client)
    r = client.get("/api/v1/admin/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["projects"] == 1
    assert body["templates"] == 1
    assert body["tables"] == 1
