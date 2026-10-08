"""Public client configuration and rule activation API."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.db.models import StandardVersion
from app.db.seed import sync_user_standard
from app.db.session import SessionLocal


def test_client_config_and_rules_expose_active_bundle(client: TestClient) -> None:
    config_response = client.get("/api/v1/client-config")
    rules_response = client.get("/api/v1/client-rules")

    assert config_response.status_code == 200, config_response.text
    assert rules_response.status_code == 200, rules_response.text
    config = config_response.json()
    rules = rules_response.json()

    assert config["client_code"] == "THALES"
    assert config["bundle"] == "thales_rules"
    assert config["bundle_version"] == "1.2.9"
    assert config["bundle_hash"]
    assert config["mapping"]["fields"]["meta_pnr_number"]["type"] == "string_list"
    assert config["catalogs"][0]["code"] == "THALES-CUSTOM"
    assert len(rules) == 66
    assert all(rule["active"] for rule in rules)
    assert all(rule["description"] and rule["message"] for rule in rules)


def test_client_rule_toggle_survives_bundle_catalog_resync(client: TestClient) -> None:
    config = client.get("/api/v1/client-config").json()
    version_id = uuid.UUID(config["catalogs"][0]["standard_version_id"])
    rule_code = "CUSTOM_CMM_NUMBER"

    disabled = client.patch(
        f"/api/v1/client-rules/{rule_code}",
        json={"active": False},
    )

    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["active"] is False

    with SessionLocal() as session:
        version = session.get(StandardVersion, version_id)
        assert version is not None
        assert rule_code in json.loads(version.disabled_rule_codes)
        sync_user_standard(session)
        session.refresh(version)
        assert rule_code in json.loads(version.disabled_rule_codes)

    refreshed_rules = client.get("/api/v1/client-rules").json()
    rule = next(item for item in refreshed_rules if item["code"] == rule_code)
    assert rule["active"] is False

    enabled = client.patch(
        f"/api/v1/client-rules/{rule_code}",
        json={"active": True},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["active"] is True


def test_client_rule_toggle_rejects_unknown_codes(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/client-rules/UNKNOWN_RULE",
        json={"active": False},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "CLIENT_RULE_NOT_FOUND"