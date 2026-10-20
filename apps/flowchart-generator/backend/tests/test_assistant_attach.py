"""Tests des pieces jointes de l'assistant (fichiers synthetiques generes en test)."""

from __future__ import annotations

import io
import zipfile

ATTACH = "/api/v1/assistant/attach"


def _docx(paragraphs: list[str]) -> bytes:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", xml)
    return buf.getvalue()


def test_attach_dsl_imports_graph(client, sample_dsl):
    res = client.post(ATTACH, files={"file": ("procedure.dsl", sample_dsl.encode(), "text/plain")})
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "graph"
    assert body["name"] == "procedure.dsl"
    assert any(n["id"] == "C1" for n in body["graph"]["nodes"])


def test_attach_csv_imports_graph(client):
    csv = "id;libelle;type;suivants\nS;Panne;start;C1\nC1;Fusible OK ?;check;F\nF;Fin;end;\n"
    res = client.post(ATTACH, files={"file": ("etapes.csv", csv.encode(), "text/csv")})
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "graph"
    assert len(body["graph"]["nodes"]) == 3


def test_attach_text_document(client):
    text = "Manuel atelier : verifier la courroie puis la tension de charge."
    res = client.post(ATTACH, files={"file": ("manuel.txt", text.encode(), "text/plain")})
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "document"
    assert body["graph"] is None
    assert "courroie" in body["text"]


def test_attach_docx_document(client):
    content = _docx(["Procedure alternateur", "Mesurer 14 V moteur tournant"])
    res = client.post(ATTACH, files={"file": ("proc.docx", content, "application/octet-stream")})
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "document"
    assert "Mesurer 14 V" in body["text"]


def test_attach_rejects_unknown_type(client):
    res = client.post(ATTACH, files={"file": ("photo.exe", b"MZ", "application/octet-stream")})
    assert res.status_code == 415
    assert res.json()["code"] == "FILE_TYPE"


def _xlsx(sheets: dict[str, list[list[object]]]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_attach_business_workbook_becomes_document(client):
    content = _xlsx(
        {
            "Pieces": [["Reference", "Designation"], ["P-104", "Relais demarreur"]],
            "Historique": [["Date", "Panne"], ["2026-01-12", "Batterie HS"]],
        }
    )
    res = client.post(ATTACH, files={"file": ("pieces.xlsx", content, "application/octet-stream")})
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "document"
    assert body["graph"] is None
    assert "Feuille : Pieces" in body["text"]
    assert "P-104 | Relais demarreur" in body["text"]
    assert "Batterie HS" in body["text"]


def test_attach_steps_workbook_still_imports_graph(client):
    content = _xlsx(
        {
            "Etapes": [
                ["ID", "Libelle", "Type", "Suivants"],
                ["S", "Panne", "start", "F"],
                ["F", "Fin", "end", ""],
            ]
        }
    )
    res = client.post(ATTACH, files={"file": ("etapes.xlsx", content, "application/octet-stream")})
    assert res.status_code == 200
    assert res.json()["kind"] == "graph"


def test_attach_business_csv_becomes_document(client):
    csv = "reference;quantite\nP-104;2\n"
    res = client.post(ATTACH, files={"file": ("stock.csv", csv.encode(), "text/csv")})
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "document"
    assert "P-104" in body["text"]


def test_chat_accepts_ten_documents(client):
    docs = [{"name": f"doc{i}.txt", "text": f"Consigne {i}"} for i in range(10)]
    res = client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "?"}], "documents": docs},
    )
    assert res.status_code == 200


def test_chat_rejects_eleven_documents(client):
    docs = [{"name": f"doc{i}.txt", "text": "x"} for i in range(11)]
    res = client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "?"}], "documents": docs},
    )
    assert res.status_code == 422


def test_attach_rejects_empty_document(client):
    res = client.post(ATTACH, files={"file": ("vide.txt", b"   ", "text/plain")})
    assert res.status_code == 422
    assert res.json()["code"] == "FILE_EMPTY"


def test_chat_imports_pasted_dsl(client, sample_dsl):
    res = client.post("/api/v1/assistant/chat", json={"messages": [{"role": "user", "content": sample_dsl}]})
    assert res.status_code == 200
    body = res.json()
    assert body["changed"] is True
    assert body["llm_used"] is False
    assert body["graph"]["title"] == "Batterie ne charge pas"


def test_chat_sends_documents_to_llm(client, monkeypatch):
    from app.flow import assistant as assistant_mod

    captured: dict = {}

    class FakeClient:
        async def chat_stream(self, messages, temperature=0.1):
            captured["messages"] = messages
            yield '{"reply": "Lu.", "graph": null}'

    monkeypatch.setattr(assistant_mod.MistralClient, "from_db", classmethod(lambda cls, db: FakeClient()))
    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "messages": [{"role": "user", "content": "Genere le plan"}],
            "documents": [{"name": "manuel.txt", "text": "Couple de serrage 25 Nm"}],
        },
    )
    assert res.status_code == 200
    system = captured["messages"][0]["content"]
    assert "manuel.txt" in system
    assert "25 Nm" in system


def test_chat_fallback_uses_document(client):
    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "messages": [{"role": "user", "content": "?"}],
            "documents": [{"name": "proc.txt", "text": "Verifier le fusible\nRemplacer le relais\nEssai"}],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["changed"] is True
    assert len(body["graph"]["nodes"]) >= 3
