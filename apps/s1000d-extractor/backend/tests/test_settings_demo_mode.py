from pathlib import Path


def test_demo_mode_defaults_off_and_persists_settings(client) -> None:
    settings = client.get("/api/v1/settings")
    assert settings.status_code == 200
    assert settings.json()["demo_enabled"] is False

    enabled = client.post("/api/v1/settings", json={"demo_enabled": True})
    assert enabled.status_code == 200
    assert enabled.json()["demo_enabled"] is True

    persisted = client.get("/api/v1/settings")
    assert persisted.status_code == 200
    assert persisted.json()["demo_enabled"] is True

    disabled = client.post("/api/v1/settings", json={"demo_enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["demo_enabled"] is False


def test_demo_mode_isolates_history_files_and_brex(client, pdf_bytes, brex_xml) -> None:
    normal_document = client.post(
        "/api/v1/documents",
        files={"file": ("normal.pdf", pdf_bytes, "application/pdf")},
        data={"s1000d_issue": "4.2"},
    )
    assert normal_document.status_code == 201, normal_document.text
    normal_id = normal_document.json()["id"]

    normal_profile = client.post(
        "/api/v1/brex",
        files={"file": ("normal.brex", brex_xml.encode("utf-8"))},
        data={"name": "Normal profile", "s1000d_issue": "4.2"},
    )
    assert normal_profile.status_code == 201, normal_profile.text
    normal_brex_id = normal_profile.json()["id"]

    normal_version = client.post(
        f"/api/v1/documents/{normal_id}/dm-versions/DMC-NORMAL",
        json={"content": "<dmodule>normal</dmodule>"},
    )
    assert normal_version.status_code == 200, normal_version.text
    normal_version_id = normal_version.json()["id"]
    normal_mapping = client.get("/api/v1/migration-inputs").json()

    from app.db.models import Document
    from app.db.session import DemoSessionLocal, SessionLocal

    with SessionLocal() as db:
        normal_path = Path(db.get(Document, normal_id).storage_path)

    enabled = client.post("/api/v1/settings", json={"demo_enabled": True})
    assert enabled.status_code == 200
    assert client.get("/api/v1/documents").json() == []
    assert client.get("/api/v1/brex").json() == []
    assert client.get("/api/v1/migration-inputs").json()["files"] == {}
    assert client.get(f"/api/v1/documents/{normal_id}").status_code == 404
    assert client.get(
        f"/api/v1/documents/{normal_id}/dm-versions/{normal_version_id}"
    ).status_code == 404

    rejected_brex_assignment = client.post(
        "/api/v1/documents",
        files={"file": ("demo-with-normal-brex.pdf", pdf_bytes, "application/pdf")},
        data={"s1000d_issue": "4.2", "brex_id": normal_brex_id},
    )
    assert rejected_brex_assignment.status_code == 409
    assert rejected_brex_assignment.json()["code"] == "DEMO_BREX_DISABLED"

    demo_document = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", pdf_bytes, "application/pdf")},
        data={"s1000d_issue": "4.2"},
    )
    assert demo_document.status_code == 201, demo_document.text
    demo_id = demo_document.json()["id"]
    demo_version = client.post(
        f"/api/v1/documents/{demo_id}/dm-versions/DMC-DEMO",
        json={"content": "<dmodule>demo</dmodule>"},
    )
    assert demo_version.status_code == 200, demo_version.text

    with DemoSessionLocal() as db:
        demo_path = Path(db.get(Document, demo_id).storage_path)
    assert demo_path.parent != normal_path.parent
    assert client.get("/api/v1/migration-inputs/document").content == pdf_bytes
    assert client.get("/api/v1/brex").json() == []

    rejected_profile = client.post(
        "/api/v1/brex",
        files={"file": ("demo.brex", brex_xml.encode("utf-8"))},
        data={"name": "Demo profile", "s1000d_issue": "4.2"},
    )
    assert rejected_profile.status_code == 409
    assert rejected_profile.json()["code"] == "DEMO_BREX_DISABLED"
    rejected_rules = client.post(
        f"/api/v1/documents/{demo_id}/resources/brex_rules",
        files={"file": ("demo-rules.json", b"{}")},
    )
    assert rejected_rules.status_code == 409
    assert rejected_rules.json()["code"] == "DEMO_BREX_DISABLED"

    disabled = client.post("/api/v1/settings", json={"demo_enabled": False})
    assert disabled.status_code == 200
    assert client.get("/api/v1/settings").json()["demo_enabled"] is False
    assert [item["id"] for item in client.get("/api/v1/documents").json()] == [normal_id]
    assert [item["id"] for item in client.get("/api/v1/brex").json()] == [normal_brex_id]
    assert client.get("/api/v1/migration-inputs").json() == normal_mapping
    assert client.get(f"/api/v1/documents/{normal_id}/dm-versions").json()[0]["id"] == normal_version_id
    assert client.get(f"/api/v1/documents/{demo_id}").status_code == 404

    enabled_again = client.post("/api/v1/settings", json={"demo_enabled": True})
    assert enabled_again.status_code == 200
    assert client.get("/api/v1/settings").json()["demo_enabled"] is True
    assert [item["id"] for item in client.get("/api/v1/documents").json()] == [demo_id]
    assert client.get(f"/api/v1/documents/{normal_id}").status_code == 404
    assert client.get(f"/api/v1/documents/{demo_id}/dm-versions").json()[0]["id"] == demo_version.json()["id"]


def test_settings_reject_removed_provider_configuration(client) -> None:
    response = client.post("/api/v1/settings", json={"api_key": "synthetic-key"})
    assert response.status_code == 422
    openapi = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/settings/test" not in openapi["paths"]


    def test_both_mode_databases_are_migrated_separately(tmp_path, monkeypatch) -> None:
        from sqlalchemy import create_engine, inspect
        from sqlalchemy.engine import make_url

        from app.db import migrations

        normal_path = tmp_path / "normal-migration-test.db"
        demo_path = tmp_path / "demo-migration-test.db"
        monkeypatch.setattr(migrations.settings, "database_url", f"sqlite:///{normal_path.as_posix()}")
        monkeypatch.setattr(migrations, "demo_database_url", make_url(f"sqlite:///{demo_path.as_posix()}"))

        migrations.upgrade_all_databases()

        for path in (normal_path, demo_path):
            engine = create_engine(f"sqlite:///{path.as_posix()}")
            try:
                tables = set(inspect(engine).get_table_names())
                assert {"app_config", "documents", "brex_profiles", "dm_versions"} <= tables
            finally:
                engine.dispose()
