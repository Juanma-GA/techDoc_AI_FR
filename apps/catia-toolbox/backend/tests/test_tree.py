"""Tests route /api/v1/imports/{id}/tree."""

from __future__ import annotations


def _scan(client, path: str) -> str:
    r = client.post("/api/v1/imports/scan", json={"path": path})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_tree_nested_structure(client, synthetic_tree) -> None:
    imp_id = _scan(client, str(synthetic_tree))
    r = client.get(f"/api/v1/imports/{imp_id}/tree")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["node_count"] > 0
    assert "metrics" in body
    # au moins une racine avec des enfants imbriques
    assert isinstance(body["nodes"], list) and body["nodes"]

    def _has_children(nodes) -> bool:
        return any(n["children"] for n in nodes)

    assert _has_children(body["nodes"])


def test_tree_404(client) -> None:
    r = client.get("/api/v1/imports/00000000-0000-0000-0000-000000000000/tree")
    assert r.status_code == 404
