"""Tests Etape 5 - checklist Controle Qualite."""

from __future__ import annotations


def test_create_template_checklist(client):
    r = client.post("/api/v1/qc/checklists", json={"title": "QC Lot 3", "template": "assembly"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "QC Lot 3"
    assert len(body["items"]) >= 8
    assert body["summary"]["total"] == len(body["items"])
    assert body["summary"]["pending"] == len(body["items"])


def test_custom_items_and_update(client):
    r = client.post("/api/v1/qc/checklists", json={
        "title": "Custom",
        "items": [{"label": "Verif A", "category": "Cat1"}, {"label": "Verif B", "category": "Cat2"}],
    })
    cid = r.json()["id"]
    items = r.json()["items"]
    assert [i["label"] for i in items] == ["Verif A", "Verif B"]

    # Mettre un item a OK avec commentaire.
    item_id = items[0]["id"]
    up = client.patch(f"/api/v1/qc/items/{item_id}", json={"status": "ok", "comment": "RAS"})
    assert up.status_code == 200, up.text
    assert up.json()["status"] == "ok"
    assert up.json()["comment"] == "RAS"

    got = client.get(f"/api/v1/qc/checklists/{cid}").json()
    assert got["summary"]["ok"] == 1
    assert got["summary"]["done"] == 1


def test_invalid_status(client):
    cid = client.post("/api/v1/qc/checklists", json={"items": [{"label": "X"}]}).json()
    item_id = cid["items"][0]["id"]
    r = client.patch(f"/api/v1/qc/items/{item_id}", json={"status": "maybe"})
    assert r.status_code == 400
    assert r.json()["code"] == "STATUS_INVALID"


def test_export_csv(client):
    cid = client.post("/api/v1/qc/checklists", json={"template": "assembly"}).json()["id"]
    r = client.get(f"/api/v1/qc/checklists/{cid}/export.csv")
    assert r.status_code == 200
    assert r.text.splitlines()[0].startswith("categorie;")
