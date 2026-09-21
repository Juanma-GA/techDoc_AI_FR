"""CRUD coverage for /api/v1/standards and version sub-resources."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_standards_returns_builtin_pdf_norms(client: TestClient) -> None:
    resp = client.get("/api/v1/standards")
    assert resp.status_code == 200
    body = resp.json()
    codes = {s["code"] for s in body}
    # Les normes purement XML/données (S1000D, ATA2200, S2000M) ont été
    # retirées du catalogue — seules restent les normes texte/rendu.
    assert codes == {"ASD-STE100", "MAT10000", "ATA100", "THALES-CUSTOM"}
    for std in body:
        assert std["builtin"] is True
        assert len(std["versions"]) >= 1


def test_create_custom_standard_and_version(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/standards",
        json={"code": "MYCO-DOC", "label": "My Company Doc", "description": "demo"},
    )
    assert resp.status_code == 201, resp.text
    std = resp.json()
    assert std["builtin"] is False
    std_id = std["id"]

    resp = client.post(
        f"/api/v1/standards/{std_id}/versions",
        json={"label": "v1", "catalog": []},
    )
    assert resp.status_code == 201
    ver = resp.json()
    assert ver["label"] == "v1"
    assert ver["builtin"] is False


def test_delete_builtin_standard_refused(client: TestClient) -> None:
    resp = client.get("/api/v1/standards")
    builtin = next(s for s in resp.json() if s["code"] == "MAT10000")
    delete = client.delete(f"/api/v1/standards/{builtin['id']}")
    assert delete.status_code == 409
    assert delete.json()["code"] == "STANDARD_BUILTIN_PROTECTED"


def test_patch_builtin_standard_refused(client: TestClient) -> None:
    resp = client.get("/api/v1/standards")
    builtin = next(s for s in resp.json() if s["code"] == "ATA100")
    patched = client.patch(
        f"/api/v1/standards/{builtin['id']}",
        json={"label": "Hacked"},
    )
    assert patched.status_code == 409


def test_version_detail_returns_catalog(client: TestClient) -> None:
    resp = client.get("/api/v1/standards")
    mat = next(s for s in resp.json() if s["code"] == "MAT10000")
    ver_id = mat["versions"][0]["id"]
    resp = client.get(f"/api/v1/standards/{mat['id']}/versions/{ver_id}")
    assert resp.status_code == 200
    detail = resp.json()
    catalog_codes = {item["code"] for item in detail["catalog"]}
    assert "MAT_FIELD_PERIODICITE" in catalog_codes
    assert "MAT_STEP_VERB" in catalog_codes


def test_thales_catalog_assigns_rule_specific_severity(client: TestClient) -> None:
    standards = client.get("/api/v1/standards")
    custom = next(item for item in standards.json() if item["code"] == "THALES-CUSTOM")
    version_id = custom["versions"][0]["id"]

    response = client.get(
        f"/api/v1/standards/{custom['id']}/versions/{version_id}"
    )

    assert response.status_code == 200
    severities = {
        item["code"]: item["severity"] for item in response.json()["catalog"]
    }
    assert severities == {
        "CUSTOM_CMM_NUMBER": "error",
        "CUSTOM_CMM_NUMBER_FONT_SIZE": "error",
        "CUSTOM_THALES_LOGO_FONT_SIZE": "warning",
        "CUSTOM_TP1_THALES_LOGO_FONT_SIZE": "warning",
        "CUSTOM_TP2_IMPORTANT_NOTICE": "error",
        "CUSTOM_TITLE_PAGE_COPYRIGHT": "warning",
        "CUSTOM_FOOTER_PAGE_NUMBER": "error",
        "CUSTOM_TP1_REVISION_NUMBER": "error",
        "CUSTOM_TP1_FIRST_ISSUE_DATE": "warning",
        "CUSTOM_HIGHLIGHTS_REVISION_HEADER": "warning",
        "CUSTOM_HIGHLIGHTS_ATA_NUMBER": "error",
        "CUSTOM_HIGHLIGHTS_PNR_HEADER": "error",
        "CUSTOM_PNR_PAGE_VALUE": "error",
        "CUSTOM_TP1_PNR_PAGE_VALUE": "error",
        "CUSTOM_REPAIR_NOTE": "error",
        "CUSTOM_TESTING_NOTE": "error",
        "CUSTOM_STORAGE_NOTE": "error",
        "CUSTOM_TP1_THALES_ADDRESS": "warning",
        "CUSTOM_DECIMAL_COMMA": "warning",
        "CUSTOM_TEMPERATURE_FAHRENHEIT": "error",
        "CUSTOM_BAR_PSI_CONVERSION": "error",
        "CUSTOM_FORBIDDEN_CONSUMABLES": "error",
        "CUSTOM_NO_DEGREE_C_SYMBOL": "info",
        "CUSTOM_NO_DEGREE_F_SYMBOL": "info",
        "CUSTOM_REVISION_LEP_STAR": "error",
        "CUSTOM_REVISION_UNDECLARED_STAR": "error",
        "CUSTOM_REVISION_LEP_DATE": "error",
        "CUSTOM_REVISION_FOOTER_DATE": "error",
        "CUSTOM_REVISION_UNDECLARED_PAGE": "error",
        "CUSTOM_REVISION_PAGE_NOT_IN_LEP": "warning",
        "CUSTOM_REVISION_MODIFIED_PAGE_ABSENT": "warning",
        "CUSTOM_HIGHLIGHTS_PAGE_PAIRING": "warning",
        "CUSTOM_HIGHLIGHTS_PAGE_LABEL_FORMAT": "warning",
    }


def test_compiled_rules_include_tp1_address_when_custom_standard_is_selected(
    client: TestClient,
) -> None:
    standards = client.get("/api/v1/standards")
    custom = next(item for item in standards.json() if item["code"] == "THALES-CUSTOM")
    version_id = custom["versions"][0]["id"]

    response = client.get(f"/api/v1/compiled-rules?standard_version_id={version_id}")

    assert response.status_code == 200
    assert "CUSTOM_TP1_THALES_ADDRESS" in {item["id"] for item in response.json()}


def test_create_duplicate_code_returns_409(client: TestClient) -> None:
    client.post("/api/v1/standards", json={"code": "UNIQ-A", "label": "A"})
    second = client.post(
        "/api/v1/standards", json={"code": "UNIQ-A", "label": "A2"}
    )
    assert second.status_code == 409
    assert second.json()["code"] == "STANDARD_CODE_TAKEN"


def test_toggle_thales_catalog_rule_individually(client: TestClient) -> None:
    standards = client.get("/api/v1/standards")
    custom = next(item for item in standards.json() if item["code"] == "THALES-CUSTOM")
    version = custom["versions"][0]
    detail_url = f"/api/v1/standards/{custom['id']}/versions/{version['id']}"
    code = "CUSTOM_CMM_NUMBER"

    disabled = client.post(
        f"{detail_url}/rules/toggle",
        json={"code": code, "enabled": False},
    )
    assert disabled.status_code == 200
    assert code in disabled.json()["disabled_rule_codes"]

    compiled = client.get(
        f"/api/v1/compiled-rules?standard_version_id={version['id']}"
    )
    assert compiled.status_code == 200
    compiled_rule = next(item for item in compiled.json() if item["id"] == code)
    assert compiled_rule["active"] is False
    assert compiled_rule["standard_id"] == custom["id"]
    assert compiled_rule["standard_version_id"] == version["id"]

    enabled = client.post(
        f"{detail_url}/rules/toggle",
        json={"code": code, "enabled": True},
    )
    assert enabled.status_code == 200
    assert code not in enabled.json()["disabled_rule_codes"]
