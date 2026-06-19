"""Admin (stats/reset) + upload BREX."""

from __future__ import annotations


def test_brex_upload_and_list(client, brex_xml) -> None:
    r = client.post(
        "/api/v1/brex",
        files={"file": ("project.brex", brex_xml.encode("utf-8"))},
        data={"name": "Projet A", "s1000d_issue": "5.0"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Projet A"
    listing = client.get("/api/v1/brex").json()
    assert len(listing) == 1


def test_bad_brex_rejected(client) -> None:
    r = client.post(
        "/api/v1/brex",
        files={"file": ("x.xml", b"<root>pas un brex</root>")},
        data={"name": "X", "s1000d_issue": "5.0"},
    )
    assert r.status_code == 422


def test_stats_and_reset_preserve_brex(client, pdf_bytes, brex_xml) -> None:
    client.post(
        "/api/v1/brex",
        files={"file": ("p.brex", brex_xml.encode("utf-8"))},
        data={"name": "P", "s1000d_issue": "5.0"},
    )
    client.post(
        "/api/v1/documents",
        files={"file": ("m.pdf", pdf_bytes)},
        data={"s1000d_issue": "5.0", "context_hint": "mixed"},
    )
    stats = client.get("/api/v1/admin/stats").json()
    assert stats["documents"] == 1 and stats["brex_profiles"] == 1

    r = client.post("/api/v1/admin/reset/documents")
    assert r.status_code == 200
    after = client.get("/api/v1/admin/stats").json()
    assert after["documents"] == 0
    assert after["brex_profiles"] == 1  # BREX preserve
