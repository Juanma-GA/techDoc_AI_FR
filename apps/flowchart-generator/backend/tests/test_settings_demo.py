"""Mode demo (preference AppConfig) et pieces jointes PDF / PPTX synthetiques."""

from __future__ import annotations

import io

SETTINGS = "/api/v1/settings"
ATTACH = "/api/v1/assistant/attach"


def test_demo_mode_defaults_to_normal(client):
    res = client.get(SETTINGS)
    assert res.status_code == 200
    assert res.json()["demo_enabled"] is False


def test_demo_mode_setting_persists_without_touching_llm(client):
    res = client.post(SETTINGS, json={"demo_enabled": True})
    assert res.status_code == 200
    assert res.json()["demo_enabled"] is True
    assert res.json()["llm_enabled"] is True
    assert client.get(SETTINGS).json()["demo_enabled"] is True
    assert client.post(SETTINGS, json={"demo_enabled": False}).json()["demo_enabled"] is False


def test_demo_mode_survives_admin_reset(client):
    client.post(SETTINGS, json={"demo_enabled": True})
    assert client.post("/api/v1/admin/reset/all").status_code == 200
    assert client.get(SETTINGS).json()["demo_enabled"] is True


def _pdf(lines: list[str]) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((72, 72 + 20 * i), line)
    data = doc.tobytes()
    doc.close()
    return data


def _pptx(title: str, body: str) -> bytes:
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = title
    slide.placeholders[1].text = body
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def test_attach_pdf_document(client):
    content = _pdf(["Consigne HSE synthetique", "Pression residuelle 0 bar avant ouverture"])
    res = client.post(ATTACH, files={"file": ("hse.pdf", content, "application/pdf")})
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "document"
    assert "Pression residuelle 0 bar" in body["text"]


def test_attach_pptx_document(client):
    content = _pptx("REX synthetique", "Fuite verin de levage : joint tige use")
    res = client.post(ATTACH, files={"file": ("rex.pptx", content, "application/octet-stream")})
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "document"
    assert "joint tige use" in body["text"]


def test_attach_invalid_pdf_is_rejected(client):
    res = client.post(ATTACH, files={"file": ("casse.pdf", b"pas un pdf", "application/pdf")})
    assert res.status_code == 422
    assert res.json()["code"] == "FILE_INVALID"
