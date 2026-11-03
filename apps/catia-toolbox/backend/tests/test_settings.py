"""Application settings remain limited to local CATIA workflows."""

from __future__ import annotations

import pytest


def test_settings_only_exposes_local_configuration(client) -> None:
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    assert set(response.json()) == {
        "onedrive_input_root",
        "onedrive_output_root",
        "composer_license_server",
        "composer_converter_path",
        "composer_settings_path",
    }


def test_settings_partial_updates_preserve_other_values(client, tmp_path) -> None:
    input_root = str(tmp_path / "input")
    output_root = str(tmp_path / "output")
    response = client.post("/api/v1/settings", json={
        "onedrive_input_root": input_root,
        "onedrive_output_root": output_root,
        "composer_license_server": "4085@synthetic-server",
    })
    assert response.status_code == 200
    response = client.post("/api/v1/settings", json={"composer_license_server": "4085@updated-server"})
    assert response.status_code == 200
    body = client.get("/api/v1/settings").json()
    assert body["onedrive_input_root"] == input_root
    assert body["onedrive_output_root"] == output_root
    assert body["composer_license_server"] == "4085@updated-server"


@pytest.mark.parametrize("field", ["api_key", "base_url", "chat_model", "embed_model", "llm_enabled"])
def test_settings_rejects_retired_fields(client, field) -> None:
    response = client.post("/api/v1/settings", json={field: "unused"})
    assert response.status_code == 422