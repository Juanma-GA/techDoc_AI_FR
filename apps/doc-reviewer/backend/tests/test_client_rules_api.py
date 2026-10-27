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
    assert config["bundle_version"] == "1.2.18"
    assert config["bundle_hash"]
    assert config["mapping"]["fields"]["meta_pnr_number"]["type"] == "string_list"
    assert config["catalogs"][0]["code"] == "THALES-CUSTOM"
    assert len(config["catalogs"]) == 2
    assert config["catalogs"][1]["code"] == "ASD-STE100"
    assert len(rules) == 87
    assert [rule["rule_number"] for rule in rules] == list(range(1, 88))
    preparation_rule_codes = {
        "CUSTOM_TP1_REVISION_NUMBER",
        "CUSTOM_TP1_THALES_ADDRESS",
        "CUSTOM_TP2_IMPORTANT_NOTICE",
        "CUSTOM_PREP_STANDARD_PRACTICE_ATA",
        "CUSTOM_PREP_STANDARD_PRACTICE_REPLACE",
        "CUSTOM_PREP_HIGHLIGHTS_REVISION_DATE",
        "CUSTOM_PREP_HIGHLIGHTS_FOOTER_DATE",
        "CUSTOM_PREP_HIGHLIGHTS_REVISION_NUMBER",
        "CUSTOM_PREP_ROR_NEW_ROW",
        "CUSTOM_PREP_LEP_MODIFIED_PAGES",
    }
    assert {
        rule["code"] for rule in rules if rule["scope"] == "preparation"
    } == preparation_rule_codes
    assert all(
        rule["scope"] == "verification"
        for rule in rules
        if rule["code"] not in preparation_rule_codes
    )
    thales_rules = [rule for rule in rules if rule["bundle_code"] == "thales_rules"]
    ste_rules = [rule for rule in rules if rule["bundle_code"] == "ste100_rules"]
    assert all(rule["active"] for rule in thales_rules)
    assert ste_rules and all(not rule["active"] for rule in ste_rules)
    assert all(rule["description"] and rule["message"] for rule in rules)
    ste_rule = next(rule for rule in rules if rule["code"] == "STE_NO_MAYBE")
    assert ste_rule["bundle_code"] == "ste100_rules"
    assert ste_rule["bundle_label"] == "ASD-STE100"
    assert ste_rule["catalog_code"] == "ASD-STE100"


def test_client_rule_toggle_survives_bundle_catalog_resync(client: TestClient) -> None:
    config = client.get("/api/v1/client-config").json()
    version_id = uuid.UUID(config["catalogs"][0]["standard_version_id"])
    rule_code = "CUSTOM_CMM_NUMBER"
    rule_number = next(
        rule["rule_number"]
        for rule in client.get("/api/v1/client-rules").json()
        if rule["code"] == rule_code
    )

    disabled = client.patch(
        f"/api/v1/client-rules/{rule_code}",
        json={"active": False},
    )

    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["active"] is False
    assert disabled.json()["rule_number"] == rule_number
    assert disabled.json()["scope"] == "verification"

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
    assert enabled.json()["rule_number"] == rule_number
    assert enabled.json()["scope"] == "verification"


def test_client_rule_toggle_rejects_unknown_codes(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/client-rules/UNKNOWN_RULE",
        json={"active": False},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "CLIENT_RULE_NOT_FOUND"


def test_ste_rule_toggle_uses_the_ste100_catalog(client: TestClient) -> None:
    config = client.get("/api/v1/client-config").json()
    ste_version_id = uuid.UUID(config["catalogs"][1]["standard_version_id"])
    rule_code = "STE_NO_MAYBE"

    disabled = client.patch(
        f"/api/v1/client-rules/{rule_code}",
        json={"active": False},
    )

    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["catalog_code"] == "ASD-STE100"
    assert disabled.json()["active"] is False

    with SessionLocal() as session:
        version = session.get(StandardVersion, ste_version_id)
        assert version is not None
        assert rule_code in json.loads(version.disabled_rule_codes)

    enabled = client.patch(
        f"/api/v1/client-rules/{rule_code}",
        json={"active": True},
    )

    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["active"] is True

    with SessionLocal() as session:
        sync_user_standard(session)

    refreshed = client.get("/api/v1/client-rules").json()
    assert next(item for item in refreshed if item["code"] == rule_code)["active"] is True