"""Full history round trips and isolation from startup state."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

BASE = "/api/v1/image-processor/history"
PRESET = "/api/v1/image-processor/workspace/excel"


def test_full_history_restores_all_state(workspace_client, workspace_state) -> None:
    workspace_state["revisions"][0]["analysis"] = {
        "width": 2480,
        "height": 3508,
        "source_width": 120,
        "source_height": 80,
        "full_text": "34708SM\n34708SM2",
        "lines": [],
        "references": [{
            "reference": "34708SM",
            "found": True,
            "line_indices": [0],
            "partial_line_indices": [1],
            "replacement": "28",
            "replacement_count": 1,
        }],
        "filename": "ICN-TEST.jpg",
    }
    history_id = str(uuid4())
    created = workspace_client.put(f"{BASE}/{history_id}", json=workspace_state)
    assert created.status_code == 200
    assert created.json()["version"] == 1
    assert created.json()["filename"] == "ICN-TEST.jpg"
    assert created.json()["piece_name"] == "Synthetic pump"
    assert created.json()["operation_count"] == 1
    restored = workspace_client.get(f"{BASE}/{history_id}")
    assert restored.status_code == 200
    saved = restored.json()["state"]
    assert saved["image"]["data_url"] == workspace_state["image"]["data_url"]
    assert saved["image"]["name"] == "synthetic.png"
    assert saved["output_filename"] == restored.json()["filename"] == "ICN-TEST.jpg"
    assert saved["revisions"][0]["image"]["data_url"] == workspace_state["image"]["data_url"]
    assert saved["revisions"][0]["analysis"]["references"][0]["partial_line_indices"] == [1]
    assert saved["excel"]["pieceRow"] == "2"
    assert saved["excel"]["pairs"][0]["enabled"] is False
    assert saved["manualPairs"] == workspace_state["manualPairs"]
    assert len(saved["operations"]) == 1
    assert workspace_client.get(PRESET).json()["workbook"] is None

    workspace_state["operations"].append({"kind": "undo", "at": "2026-10-16T11:00:00Z"})
    workspace_state["revisions"] = []
    updated = workspace_client.put(f"{BASE}/{history_id}", json=workspace_state)
    assert updated.json()["version"] == 2
    assert updated.json()["created_at"] == created.json()["created_at"]
    latest = workspace_client.get(f"{BASE}/{history_id}").json()["state"]
    assert latest["revisions"] == []
    assert [operation["kind"] for operation in latest["operations"]] == ["brush-color", "undo"]
    assert len(workspace_client.get(BASE).json()["items"]) == 1


def test_lightweight_history_cursor_listing(workspace_client, workspace_state) -> None:
    ids = []
    for index in range(3):
        history_id = str(uuid4())
        ids.append(history_id)
        workspace_state["image"]["name"] = f"synthetic-{index}.png"
        assert workspace_client.put(f"{BASE}/{history_id}", json=workspace_state).status_code == 200
    first = workspace_client.get(BASE, params={"limit": 2}).json()
    assert len(first["items"]) == 2
    assert first["items"][0]["id"] == ids[2]
    assert first["items"][0]["filename"] == "ICN-TEST.jpg"
    assert "state" not in first["items"][0]
    assert "data_url" not in str(first)
    second = workspace_client.get(BASE, params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert len(second["items"]) == 1
    assert second["items"][0]["id"] == ids[0]
    assert second["items"][0]["filename"] == "ICN-TEST.jpg"
    assert second["next_cursor"] is None
    assert workspace_client.get(BASE, params={"limit": 101}).status_code == 422


@pytest.mark.parametrize("with_analysis", [False, True])
def test_old_history_names_use_icn_without_rewriting_source(
    workspace_client, workspace_state, with_analysis,
) -> None:
    from app.db.models import ImageHistory
    from app.db.session import get_db

    if with_analysis:
        workspace_state["revisions"][0]["analysis"] = {
            "width": 20, "height": 30, "source_width": 20, "source_height": 30,
            "full_text": "", "lines": [], "references": [], "filename": "ICN-TEST.jpg",
        }
    history_id = str(uuid4())
    assert workspace_client.put(f"{BASE}/{history_id}", json=workspace_state).status_code == 200
    with next(workspace_client.app.dependency_overrides[get_db]()) as db:
        record = db.get(ImageHistory, history_id)
        state = json.loads(record.state)
        state.pop("output_filename")
        record.state = json.dumps(state)
        record.filename = "old-source-retouched.png"
        db.commit()
    listed = workspace_client.get(BASE)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["filename"] == "ICN-TEST.jpg"
    restored = workspace_client.get(f"{BASE}/{history_id}").json()
    assert restored["filename"] == "ICN-TEST.jpg"
    assert restored["state"]["image"]["name"] == "synthetic.png"


def test_delete_history_preserves_startup_excel(workspace_client, workspace_state, excel_preset) -> None:
    history_id = str(uuid4())
    workspace_client.put(PRESET, json=excel_preset)
    workspace_client.put(f"{BASE}/{history_id}", json=workspace_state)
    assert workspace_client.delete(f"{BASE}/{history_id}").status_code == 204
    assert workspace_client.get(f"{BASE}/{history_id}").status_code == 404
    assert workspace_client.delete(f"{BASE}/{history_id}").status_code == 404
    assert workspace_client.get(PRESET).json()["sheet"] == "Parts"
    assert workspace_client.get(BASE).json()["items"] == []


def test_history_validation(workspace_client, workspace_state) -> None:
    assert workspace_client.get(f"{BASE}/not-a-uuid").status_code == 422
    workspace_state["image"]["data_url"] = "data:image/png;base64,bm90IGFuIGltYWdl"
    response = workspace_client.put(f"{BASE}/{uuid4()}", json=workspace_state)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert workspace_client.get(BASE).json()["items"] == []


def test_admin_stats_and_resets_cover_new_data(workspace_client, workspace_state, excel_preset) -> None:
    workspace_client.put(PRESET, json=excel_preset)
    workspace_client.put(f"{BASE}/{uuid4()}", json=workspace_state)
    workspace_client.post("/api/v1/settings", json={"demo_enabled": True})
    stats = workspace_client.get("/api/v1/admin/stats").json()
    assert stats["documents"] == stats["sessions"] == stats["messages"] == 1
    assert stats["total_size_bytes"] > 0

    scoped = workspace_client.post("/api/v1/admin/reset/history").json()
    assert scoped["deleted"] == {"history": 1}
    assert workspace_client.get(PRESET).json()["workbook"] is not None
    workspace_client.put(f"{BASE}/{uuid4()}", json=workspace_state)
    reset = workspace_client.post("/api/v1/admin/reset/all").json()
    assert reset["deleted"] == {"history": 1, "excel_presets": 1}
    assert workspace_client.get(PRESET).json()["workbook"] is None
    assert workspace_client.get("/api/v1/settings").json()["demo_enabled"] is True
