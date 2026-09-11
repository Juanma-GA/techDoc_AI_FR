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
    assert codes == {"ASD-STE100", "MAT10000", "ATA100", "ATEXIS-CUSTOM"}
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


def test_compiled_rules_include_tp1_address_when_custom_standard_is_selected(
    client: TestClient,
) -> None:
    standards = client.get("/api/v1/standards")
    custom = next(item for item in standards.json() if item["code"] == "ATEXIS-CUSTOM")
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
