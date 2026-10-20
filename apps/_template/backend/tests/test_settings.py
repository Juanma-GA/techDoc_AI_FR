from __future__ import annotations


def test_demo_mode_defaults_to_normal(client) -> None:
    response = client.get("/api/v1/settings")

    assert response.status_code == 200
    assert response.json() == {"demo_enabled": False}


def test_demo_mode_setting_persists(client) -> None:
    response = client.post("/api/v1/settings", json={"demo_enabled": True})

    assert response.status_code == 200
    assert response.json() == {"demo_enabled": True}
    assert client.get("/api/v1/settings").json() == {"demo_enabled": True}
