"""Synthetic startup preferences: preserve Excel, never image or selected part."""

from __future__ import annotations

import base64
from hashlib import sha256

import pytest

BASE = "/api/v1/image-replace/workspace/excel"


def test_empty_startup_preferences(workspace_client) -> None:
    response = workspace_client.get(BASE)
    assert response.status_code == 200
    assert response.json()["workbook"] is None
    assert "pieceRow" not in response.json()
    assert "image" not in response.json()


def test_excel_mapping_round_trip_and_removal(workspace_client, excel_preset) -> None:
    response = workspace_client.put(BASE, json=excel_preset)
    assert response.status_code == 200
    stored = response.json()
    contents = base64.b64decode(excel_preset["workbook"]["data_url"].split(",")[1])
    assert stored["workbook"]["sha256"] == sha256(contents).hexdigest()
    assert workspace_client.get(BASE).json() == stored
    assert workspace_client.put(BASE, json=stored).status_code == 200
    assert stored["sheet"] == "Parts"
    assert stored["pieceColumn"] == "4"
    assert stored["pieces"] == excel_preset["pieces"]

    assert workspace_client.put(BASE, json={}).status_code == 200
    assert workspace_client.get(BASE).json()["workbook"] is None


@pytest.mark.parametrize("field", ["image", "pieceRow", "pairs", "manualPairs"])
def test_startup_rejects_image_and_part_selection(workspace_client, excel_preset, field) -> None:
    response = workspace_client.put(BASE, json={**excel_preset, field: "not allowed"})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("changes", [
    {"data_url": "not a data URL"},
    {"data_url": "data:application/octet-stream;base64,@@@"},
    {"data_url": "data:application/octet-stream;base64,"},
    {"sha256": "incorrect"},
])
def test_invalid_saved_files_are_explicit_errors(workspace_client, excel_preset, changes) -> None:
    excel_preset["workbook"].update(changes)
    response = workspace_client.put(BASE, json=excel_preset)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert all("input" not in item for item in response.json()["detail"])
