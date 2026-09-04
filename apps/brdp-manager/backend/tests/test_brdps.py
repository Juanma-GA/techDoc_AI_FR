"""POST/PUT/DELETE /api/v1/brdps — H-NEW-09 remediation.

Covers: normal CRUD still works, and both delete endpoints (single + bulk)
now require a confirm_token (HR9 / rule #13 server-side backstop).
"""

from __future__ import annotations


def _create(client, id="B-1", **overrides):
    payload = {"id": id, "identifier": id, "title": "T", "definition": "D", "proposal": "P"}
    payload.update(overrides)
    res = client.post("/api/v1/brdps", json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def test_create_list_update_roundtrip(client) -> None:
    _create(client, id="B-1", title="Original")
    res = client.put("/api/v1/brdps/B-1", json={"id": "B-1", "title": "Updated"})
    assert res.status_code == 200
    assert res.json()["title"] == "Updated"

    listed = client.get("/api/v1/brdps").json()
    assert [b["id"] for b in listed] == ["B-1"]


def test_delete_single_without_token_rejected(client) -> None:
    _create(client, id="B-1")
    res = client.delete("/api/v1/brdps/B-1")
    assert res.status_code == 422
    # Not confirmed -> still there.
    assert [b["id"] for b in client.get("/api/v1/brdps").json()] == ["B-1"]


def test_delete_single_with_short_token_rejected(client) -> None:
    _create(client, id="B-1")
    res = client.delete("/api/v1/brdps/B-1?confirm_token=short")
    assert res.status_code == 422
    assert [b["id"] for b in client.get("/api/v1/brdps").json()] == ["B-1"]


def test_delete_single_with_valid_token_removes_only_that_item(client) -> None:
    _create(client, id="B-1")
    _create(client, id="B-2")

    res = client.delete("/api/v1/brdps/B-1?confirm_token=ui-confirmed-delete")
    assert res.status_code == 200

    remaining = [b["id"] for b in client.get("/api/v1/brdps").json()]
    assert remaining == ["B-2"]  # only B-1 was removed, B-2 untouched


def test_delete_all_without_token_rejected(client) -> None:
    _create(client, id="B-1")
    res = client.delete("/api/v1/brdps")
    assert res.status_code == 422
    assert len(client.get("/api/v1/brdps").json()) == 1


def test_delete_all_with_valid_token_wipes_table(client) -> None:
    _create(client, id="B-1")
    _create(client, id="B-2")
    res = client.delete("/api/v1/brdps?confirm_token=ui-confirmed-delete")
    assert res.status_code == 200
    assert client.get("/api/v1/brdps").json() == []
