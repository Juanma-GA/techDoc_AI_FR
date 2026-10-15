import json
import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from starlette.requests import Request

from app.checks.client_registry import load_active_client_configuration
from app.checks.mode_registry import analysis_standard_version_ids
from app.db.models import AnalysisRun, AppConfig
from app.db.session import SessionLocal


@pytest.fixture(autouse=True)
def clear_demo_mode_setting():
    with SessionLocal() as db:
        db.execute(delete(AppConfig).where(AppConfig.key == "demo_enabled"))
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(delete(AppConfig).where(AppConfig.key == "demo_enabled"))
        db.commit()


def test_demo_mode_defaults_to_normal_and_persists(client: TestClient) -> None:
    initial = client.get("/api/v1/settings/mistral")
    assert initial.status_code == 200
    assert initial.json()["demo_enabled"] is False

    enabled = client.post(
        "/api/v1/settings/mistral",
        json={"demo_enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["demo_enabled"] is True
    assert client.get("/api/v1/settings/mistral").json()["demo_enabled"] is True


def test_partial_mistral_update_preserves_demo_mode(client: TestClient) -> None:
    enabled = client.post(
        "/api/v1/settings/mistral",
        json={"demo_enabled": True},
    )
    assert enabled.status_code == 200

    llm_disabled = client.post(
        "/api/v1/settings/mistral",
        json={"llm_enabled": False},
    )
    assert llm_disabled.status_code == 200
    assert llm_disabled.json()["llm_enabled"] is False
    assert llm_disabled.json()["demo_enabled"] is True


def test_demo_mode_uses_only_demo_rules_and_restores_normal_states(
    client: TestClient,
) -> None:
    normal_config = client.get("/api/v1/client-config").json()
    assert normal_config["client_code"] == "THALES"
    normal_standard_codes = {
        standard["code"] for standard in client.get("/api/v1/standards").json()
    }
    assert "THALES-CUSTOM" in normal_standard_codes
    assert "DEMO-CUSTOM" not in normal_standard_codes
    normal_rules_response = client.get("/api/v1/client-rules")
    assert normal_rules_response.status_code == 200
    normal_rules = normal_rules_response.json()
    normal_rule = next(rule for rule in normal_rules if rule["code"] == "CUSTOM_CMM_NUMBER")
    original_active = normal_rule["active"]
    changed_active = not original_active
    normal_rule_code = normal_rule["code"]

    try:
        changed = client.patch(
            f"/api/v1/client-rules/{normal_rule_code}",
            json={"active": changed_active},
        )
        assert changed.status_code == 200

        enabled = client.post("/api/v1/settings/mistral", json={"demo_enabled": True})
        assert enabled.status_code == 200

        demo_config = client.get("/api/v1/client-config").json()
        demo_standard_codes = {
            standard["code"] for standard in client.get("/api/v1/standards").json()
        }
        demo_rules_response = client.get("/api/v1/client-rules")
        assert demo_rules_response.status_code == 200
        demo_rules = demo_rules_response.json()
        expected_codes = {
            "CUSTOM_PNR_PAGE_VALUE",
            "CUSTOM_HIGHLIGHTS_ATA_NUMBER",
            "CUSTOM_HIGHLIGHTS_PNR_HEADER",
            "CUSTOM_HIGHLIGHTS_REVISION_HEADER",
            "CUSTOM_CMM_NUMBER",
            "CUSTOM_REVISION_FOOTER_DATE",
            "CUSTOM_TP1_FIRST_ISSUE_DATE",
            "CUSTOM_TP1_PART_NUMBER",
            "CUSTOM_TP1_DEMO_ADDRESS",
        }

        assert demo_config["client_code"] == "DEMO"
        assert demo_config["label"] == "DEMO"
        assert "DEMO-CUSTOM" in demo_standard_codes
        assert "THALES-CUSTOM" not in demo_standard_codes
        assert {rule["code"] for rule in demo_rules} == expected_codes
        assert all(rule["active"] for rule in demo_rules)
        assert "thales" not in json.dumps(
            {"config": demo_config, "rules": demo_rules},
            ensure_ascii=False,
        ).lower()

        demo_version_id = demo_config["catalogs"][0]["standard_version_id"]
        normal_version_ids = [
            catalog["standard_version_id"] for catalog in normal_config["catalogs"]
        ]
        request = Request({"type": "http", "app": client.app})
        with SessionLocal() as db:
            assert analysis_standard_version_ids(
                request,
                db,
                normal_version_ids,
                None,
            ) == [demo_version_id]

        disabled = client.post("/api/v1/settings/mistral", json={"demo_enabled": False})
        assert disabled.status_code == 200
        with SessionLocal() as db:
            restored_version_ids = analysis_standard_version_ids(
                request,
                db,
                [demo_version_id],
                UUID(demo_version_id),
            )
        assert set(restored_version_ids) == set(normal_version_ids)

        restored_rules = {
            rule["code"]: rule
            for rule in client.get("/api/v1/client-rules").json()
        }
        assert restored_rules[normal_rule_code]["active"] is changed_active
        restored_standard_codes = {
            standard["code"] for standard in client.get("/api/v1/standards").json()
        }
        assert restored_standard_codes == normal_standard_codes
    finally:
        client.post("/api/v1/settings/mistral", json={"demo_enabled": False})
        client.patch(
            f"/api/v1/client-rules/{normal_rule_code}",
            json={"active": original_active},
        )


def test_demo_upload_uses_demo_catalog_even_with_normal_catalog_ids(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    normal_config = client.get("/api/v1/client-config").json()
    normal_version_ids = ",".join(
        catalog["standard_version_id"] for catalog in normal_config["catalogs"]
    )
    client.post("/api/v1/settings/mistral", json={"demo_enabled": True})
    demo_config = client.get("/api/v1/client-config").json()
    demo_version_id = demo_config["catalogs"][0]["standard_version_id"]

    response = client.post(
        f"/api/v1/documents?standard_version_ids={normal_version_ids}",
        files={"file": ("synthetic-demo.pdf", sample_pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["standard_version_ids"] == [demo_version_id]


def test_existing_document_analysis_uses_demo_bundle_and_catalog(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    upload = client.post(
        "/api/v1/documents",
        files={"file": ("synthetic.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    metadata = client.patch(
        f"/api/v1/documents/{document_id}",
        json={
            "meta_revision_date": "JUL 27/26",
            "meta_cmm_number": "79-30-02",
            "meta_first_issue_date": "JUL 1966",
            "meta_revision_number": "Rev. 01",
            "meta_pnr_number": "123-456-AA",
            "document_language": "en",
        },
    )
    assert metadata.status_code == 200, metadata.text

    client.post("/api/v1/settings/mistral", json={"demo_enabled": True})
    demo_config = client.get("/api/v1/client-config").json()
    demo_version_id = demo_config["catalogs"][0]["standard_version_id"]

    with client.stream("POST", f"/api/v1/documents/{document_id}/analyze") as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes())
    assert b"event: done" in body

    with SessionLocal() as db:
        run = db.scalar(
            select(AnalysisRun)
            .where(AnalysisRun.document_id == UUID(document_id))
            .order_by(AnalysisRun.started_at.desc())
        )
    assert run is not None
    snapshot = json.loads(run.context_snapshot_json)
    assert snapshot["client_bundle"]["bundle"] == "demo_rules"
    assert snapshot["client_bundle"]["client_code"] == "DEMO"
    assert run.standard_version_ids == json.dumps([demo_version_id])


def test_demo_address_rule_matches_the_requested_exact_address() -> None:
    configuration = load_active_client_configuration(
        environ={"CLIENT_BUNDLE": "demo_rules"}
    )
    address_rule = next(
        rule
        for rule in configuration.bundle.rules
        if rule.code == "CUSTOM_TP1_DEMO_ADDRESS"
    )
    pattern = address_rule.compiled_rule.checks[0].expected
    assert isinstance(pattern, str)

    address = (
        "40 Avenue de l\u2019avenue 39700 Ville - France Tel : +33 (0)6 "
        "22 22 22 22 www.logogroup.com"
    )
    assert re.search(pattern, address)
    assert re.search(pattern, address.replace("39700 Ville", "39701 Ville")) is None
