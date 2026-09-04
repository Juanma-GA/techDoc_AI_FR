"""Extraction des illustrations (JPG) + ICN sur les figures + expo API."""

from __future__ import annotations


def _upload(client, data: bytes) -> str:
    r = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", data)},
        data={"s1000d_issue": "5.0", "context_hint": "mixed"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_slugify() -> None:
    from app.core.illustrations import slugify

    assert slugify("Figure 1 Hydraulic pump location").startswith("figure-1-hydraulic")
    assert slugify("") == "illustration"


def test_images_extracted_and_served(client, pdf_bytes_image) -> None:
    doc_id = _upload(client, pdf_bytes_image)
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")

    names = client.get(f"/api/v1/documents/{doc_id}/wizard/images").json()
    assert names, "aucune illustration extraite"
    # Nommee d'apres la legende 'Figure 1 ...'.
    assert any(n.startswith("figure-1") for n in names)

    r = client.get(f"/api/v1/documents/{doc_id}/wizard/images/{names[0]}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"

    # Traversee de repertoire refusee.
    bad = client.get(f"/api/v1/documents/{doc_id}/wizard/images/..%2Fsecret.jpg")
    assert bad.status_code == 404


def test_figure_icn_in_generated_xml(client, pdf_bytes_image) -> None:
    doc_id = _upload(client, pdf_bytes_image)
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    # split -> type -> structure -> generate
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"types": {}})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"overrides": []})
    st = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert st["step"] == "generate"
    found = False
    for d in st["dms"]:
        xml = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{d['dm_id']}/xml").text
        if "figure-1" in xml and ".jpg" in xml:
            found = True
    assert found, "l'ICN de la figure n'est pas referencee dans le XML"
