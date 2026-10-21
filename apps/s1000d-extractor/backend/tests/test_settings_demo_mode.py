def test_demo_mode_defaults_off_and_persists_settings(client) -> None:
    settings = client.get("/api/v1/settings")
    assert settings.status_code == 200
    assert settings.json()["demo_enabled"] is False

    enabled = client.post("/api/v1/settings", json={"demo_enabled": True})
    assert enabled.status_code == 200
    assert enabled.json()["demo_enabled"] is True

    persisted = client.get("/api/v1/settings")
    assert persisted.status_code == 200
    assert persisted.json()["demo_enabled"] is True

    disabled = client.post("/api/v1/settings", json={"demo_enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["demo_enabled"] is False
