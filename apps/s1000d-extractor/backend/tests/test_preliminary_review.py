"""Synthetic reference procedures, persistence, decisions and export gates."""

import json
from io import BytesIO
from zipfile import ZipFile

import pymupdf as fitz
import pytest

from app.core import preliminary_review as review
from app.core import context_classifier, resolver
from app.core.ir import IRNode, to_dict
from app.core.preliminary_detection import passages
from app.db.models import Document
from app.db.session import SessionLocal


@pytest.fixture(params=["4.1", "4.2"])
def procedure(client, tmp_path, request):
    source = tmp_path / "synthetic.pdf"
    texts = [
        "Ensure the power is off.",
        "Two qualified technicians.",
        "Required tools: torque wrench.",
        "Consumables: grease.",
        "Spare parts: new gasket.",
        "WARNING: Wear protective gloves.",
        "Disconnect the connector.",
    ]
    with fitz.open() as pdf:
        for index in range(4):
            page = pdf.new_page()
            for row, text in enumerate(texts):
                page.insert_text((72, 72 + row * 24), text)
        pdf.save(str(source))
    tree = IRNode(id="root", kind="section", children=[
        IRNode(id=f"p{index}", kind="paragraph", text=text, page=1 + index % 2)
        for index, text in enumerate(texts)
    ] + [
        IRNode(id="table", kind="table", page=2,
               table_rows=[["Tool", "Qty"], ["Screwdriver", "1"]]),
    ])
    context_classifier.apply_dm_type(tree, "procedural")
    resolver.resolve(tree)
    with SessionLocal() as db:
        doc = Document(
            filename=source.name, source_format="pdf", storage_path=str(source),
            s1000d_issue=request.param, wizard_step="structure", status="wizard",
            pdf_cut_path=str(source), pdf_cut_start_page=2, pdf_cut_end_page=3,
            dms_json=json.dumps([{
                "dm_id": "proc", "dm_type": "procedural", "title": "Removal",
                "tree": to_dict(tree),
            }, {
                "dm_id": "desc", "dm_type": "descriptive", "title": "Overview",
                "tree": to_dict(IRNode(id="d", kind="section", children=[
                    IRNode(id="dp", kind="paragraph", text="A descriptive body."),
                ])),
            }]),
        )
        db.add(doc)
        db.commit()
        doc_id = doc.id
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert response.status_code == 200, response.text
    assert response.json()["step"] == "preliminary"
    return doc_id, source


def _action(client, doc_id, **kwargs):
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]
    return client.post(
        f"/api/v1/documents/{doc_id}/wizard/preliminary",
        json={"revision": state["revision"], "dm_id": "proc", **kwargs},
    )


def _finish(client, doc_id):
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]
    for passage in state["reviews"]["proc"]["passages"]:
        response = _action(
            client, doc_id, op="decide", passage_id=passage["id"],
            destination=passage["suggested"] if passage["suggested"] != "review" else "body",
        )
        assert response.status_code == 200, response.text
    done = _action(client, doc_id, op="complete", confirm_empty=True)
    assert done.status_code == 200, done.text


def test_reference_rules_cover_all_categories_and_every_source_passage(procedure, client):
    doc_id, _ = procedure
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()
    assert state["steps"] == ["split", "type", "structure", "preliminary", "generate"]
    assert set(state["preliminary"]["reviews"]) == {"proc"}
    items = state["preliminary"]["reviews"]["proc"]["passages"]
    assert len(items) == 9
    assert {p["suggested"] for p in items} >= {
        "conditions", "personnel", "support", "supplies", "spares", "safety", "body",
    }
    assert [p["suggested"] for p in items] == [
        "conditions", "personnel", "support", "supplies", "spares", "safety",
        "body", "support", "support",
    ]
    assert all(p["decision"] is None for p in items)
    assert items[0]["page"] == 2  # Original PDF page, not cut-page number.
    assert all(p["source_text"] == p["text"] for p in items)
    assert all(p["end"] - p["start"] == len(p["source_text"]) for p in items)


def test_generation_and_direct_exports_cannot_bypass_review(procedure, client):
    doc_id, _ = procedure
    assert client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).status_code == 409
    assert client.get(f"/api/v1/documents/{doc_id}/wizard/dm/proc/xml").status_code == 409
    assert client.get(f"/api/v1/documents/{doc_id}/wizard/zip").status_code == 409
    assert _action(client, doc_id, op="complete", confirm_empty=True).status_code == 409
    assert _action(client, doc_id, op="complete", confirm_empty=False).status_code == 409
    for path in ("extract", "xml"):
        response = (
            client.post(f"/api/v1/documents/{doc_id}/{path}") if path == "extract"
            else client.get(f"/api/v1/documents/{doc_id}/{path}")
        )
        assert response.status_code == 409
        assert response.json()["code"] == "WIZARD_WORKFLOW_REQUIRED"


def test_cursor_decisions_and_edits_survive_new_database_sessions(procedure, client):
    doc_id, _ = procedure
    response = _action(client, doc_id, op="decide", passage_id="p0:text:0",
                       destination="conditions", text="Power isolated.")
    assert response.status_code == 200
    response = _action(client, doc_id, op="cursor", page=3, scroll_top=1250.5,
                       selected_id="p0:text:0")
    assert response.status_code == 200
    with SessionLocal() as db:
        saved = review.view(db.get(Document, doc_id))
    current = saved["reviews"]["proc"]
    assert saved["active_dm_id"] == "proc"
    assert current["position"] == {"page": 3, "scroll_top": 1250.5, "selected_id": "p0:text:0"}
    assert current["passages"][0]["decision"] == "conditions"
    assert current["passages"][0]["text"] == "Power isolated."
    assert current["saved_at"]
    assert client.get(f"/api/v1/documents/{doc_id}/wizard").json()["step"] == "preliminary"
    response = _action(client, doc_id, op="decide", passage_id="p0:text:0", text="Power safely isolated.")
    assert response.json()["reviews"]["proc"]["passages"][0]["decision"] == "conditions"


def test_conflicting_tabs_and_invalid_input_are_rejected(procedure, client):
    doc_id, _ = procedure
    body = {"revision": 1, "dm_id": "proc", "op": "cursor", "page": 2}
    first = client.post(f"/api/v1/documents/{doc_id}/wizard/preliminary", json=body)
    assert first.status_code == 200
    second = client.post(f"/api/v1/documents/{doc_id}/wizard/preliminary", json=body)
    assert second.status_code == 409
    assert second.json()["code"] == "REVIEW_CONFLICT"
    for invalid in (
        {"op": "cursor", "page": 999},
        {"op": "cursor", "scroll_top": -1},
        {"op": "decide", "passage_id": "p0:text:0", "destination": "invented"},
        {"op": "decide", "passage_id": "p0:text:0", "text": "   "},
        {"op": "split", "passage_id": "p0:text:0", "split_at": 999},
    ):
        assert _action(client, doc_id, **invalid).status_code == 422


def test_split_preserves_exact_source_ranges(procedure, client):
    doc_id, _ = procedure
    response = _action(client, doc_id, op="split", passage_id="p0:text:0", split_at=11)
    assert response.status_code == 200, response.text
    items = response.json()["reviews"]["proc"]["passages"][:2]
    assert "".join(p["source_text"] for p in items) == "Ensure the power is off."
    assert [(p["start"], p["end"]) for p in items] == [(0, 11), (11, 24)]
    assert all(p["decision"] is None for p in items)
    assert len({p["id"] for p in items}) == 2
    _action(client, doc_id, op="decide", passage_id=items[0]["id"], text="Changed", destination="body")
    assert _action(client, doc_id, op="split", passage_id=items[0]["id"], split_at=2).status_code == 409


def test_changed_source_requires_explicit_restart(procedure, client):
    doc_id, source = procedure
    _finish(client, doc_id)
    with source.open("ab") as stream:
        stream.write(b"\n% Synthetic revision\n")
    state = client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]
    assert state["source_changed"]
    assert state["reviews"]["proc"]["status"] == "stale"
    assert client.get(f"/api/v1/documents/{doc_id}/wizard/dm/proc/xml").status_code == 409
    assert _action(client, doc_id, op="cursor", page=2).status_code == 409
    restarted = _action(client, doc_id, op="restart")
    assert restarted.status_code == 200
    assert all(p["decision"] is None for p in restarted.json()["reviews"]["proc"]["passages"])


def test_pdf_pages_and_exact_source_anchors(procedure, client):
    doc_id, _ = procedure
    response = client.get(f"/api/v1/documents/{doc_id}/wizard/preliminary/proc/pages")
    assert [p["page"] for p in response.json()] == [2, 3]
    response = client.get(f"/api/v1/documents/{doc_id}/wizard/preliminary/proc/page/2")
    assert response.status_code == 200, response.text
    assert response.json()["anchors"]["p0:text:0"]
    assert client.get(f"/api/v1/documents/{doc_id}/wizard/preliminary/proc/page/4").status_code == 422


def test_decisions_drive_xml_zip_and_keep_source_immutable(procedure, client):
    doc_id, _ = procedure
    with SessionLocal() as db:
        original = json.loads(db.get(Document, doc_id).dms_json)[0]["tree"]
    _finish(client, doc_id)
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert response.status_code == 200, response.text
    assert response.json()["step"] == "generate"
    assert next(dm for dm in response.json()["dms"] if dm["dm_id"] == "proc")["xsd_valid"]
    xml = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/proc/xml")
    assert xml.status_code == 200, xml.text
    from lxml import etree
    root = etree.fromstring(xml.content)
    assert root.xpath("string(//preliminaryRqmts/reqCondGroup//reqCond)") == "Ensure the power is off."
    assert "Disconnect the connector." in root.xpath("string(//mainProcedure)")
    assert "Ensure the power is off." not in root.xpath("string(//mainProcedure)")
    assert "Screwdriver" in root.xpath("string(//reqSupportEquips)")
    download = client.get(f"/api/v1/documents/{doc_id}/wizard/zip")
    assert download.status_code == 200, download.text
    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.read("proc.xml") == xml.content
    with SessionLocal() as db:
        assert json.loads(db.get(Document, doc_id).dms_json)[0]["tree"] == original
    assert client.post(f"/api/v1/documents/{doc_id}/wizard/back").json()["step"] == "preliminary"


def test_empty_review_requires_positive_confirmation_and_word_has_reading_pages(client):
    with SessionLocal() as db:
        doc = Document(filename="empty.docx", source_format="docx", storage_path="synthetic-unused",
                       s1000d_issue="4.2", wizard_step="structure", dms_json=json.dumps([{
                           "dm_id": "proc", "dm_type": "procedural", "title": "Empty",
                           "tree": to_dict(IRNode(id="empty", kind="section")),
                       }]))
        db.add(doc)
        db.commit()
        doc_id = doc.id
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["preliminary"]["reviews"]["proc"]["status"] == "pending"
    assert _action(client, doc_id, op="complete").status_code == 409
    assert _action(client, doc_id, op="complete", confirm_empty=True).status_code == 200
    items = passages(to_dict(IRNode(id="root", kind="section", children=[
        IRNode(id="a", kind="paragraph", text="A" * 2400),
        IRNode(id="b", kind="paragraph", text="B"),
    ])), source_format="docx", page_offset=0)
    assert [p["page"] for p in items] == [1, 2]


def test_compare_and_swap_rejects_a_concurrent_database_session(procedure):
    doc_id, _ = procedure
    with SessionLocal() as first, SessionLocal() as second:
        original = first.get(Document, doc_id)
        concurrent = second.get(Document, doc_id)
        revision = review.load(original)["revision"]
        action = review.ReviewAction(revision=revision, dm_id="proc", op="cursor", page=2)
        review.apply(first, original, action)
        from app.core.errors import AppError
        with pytest.raises(AppError) as error:
            review.apply(second, concurrent, action)
        assert error.value.code == "REVIEW_CONFLICT"


def test_migration_creates_review_column_only_in_a_temporary_database(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text
    from app.config import settings
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'migration.db'}")
    config = Config()
    config.set_main_option("script_location", "alembic")
    command.upgrade(config, "0010_resource_paths")
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO documents "
            "(id, filename, source_format, storage_path, s1000d_issue, context_hint, status, created_at) "
            "VALUES ('synthetic-existing', 'synthetic-existing.pdf', 'pdf', "
            "'synthetic-unused', '4.2', 'mixed', 'uploaded', '2026-10-27 12:00:00')"
        ))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert "preliminary_review_json" in {column["name"] for column in inspect(connection).get_columns("documents")}
        assert connection.scalar(text("SELECT filename FROM documents")) == "synthetic-existing.pdf"
    command.downgrade(config, "0010_resource_paths")
    with engine.connect() as connection:
        assert "preliminary_review_json" not in {column["name"] for column in inspect(connection).get_columns("documents")}
        assert connection.scalar(text("SELECT filename FROM documents")) == "synthetic-existing.pdf"
    engine.dispose()


def test_backtracking_to_structure_preserves_review_but_reanalysis_invalidates_it(procedure, client):
    doc_id, _ = procedure
    _finish(client, doc_id)
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/back")
    assert response.json()["step"] == "structure"
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert response.json()["preliminary"]["reviews"]["proc"]["status"] == "reviewed"
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        review.invalidate_source(doc)
        db.commit()
    assert client.get(f"/api/v1/documents/{doc_id}/wizard").json()["preliminary"]["reviews"]["proc"]["status"] == "stale"


def test_wizard_never_calls_remote_typing_or_ocr(client, pdf_bytes, monkeypatch):
    from app.core import context_classifier, ocr

    def forbidden(*args, **kwargs):
        raise AssertionError("A local wizard must not consult a remote AI service")

    monkeypatch.setattr(context_classifier, "_llm_refine_dms", forbidden)
    monkeypatch.setattr(ocr, "ocr_available", forbidden)
    monkeypatch.setattr(ocr, "run_ocr", forbidden)
    uploaded = client.post(
        "/api/v1/documents", files={"file": ("synthetic.pdf", pdf_bytes)},
        data={"s1000d_issue": "4.2", "context_hint": "mixed"},
    )
    doc_id = uploaded.json()["id"]
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/start", json={"cut_pdf": False})
    assert response.status_code == 200, response.text
    assert response.json()["step"] == "split"


def test_local_ingest_rejects_mixed_scans_without_ignoring_pages_or_calling_ocr(tmp_path, monkeypatch):
    from app.core import ingest, ocr
    from app.core.errors import AppError

    def forbidden(*args, **kwargs):
        raise AssertionError("OCR must not be consulted in local mode")

    monkeypatch.setattr(ocr, "ocr_available", forbidden)
    source = tmp_path / "synthetic-mixed.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "A sufficiently long synthetic text page.")
        page = pdf.new_page()
        image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20))
        image.set_rect(image.irect, (20, 20, 20))
        page.insert_image(page.rect, pixmap=image)
        pdf.new_page()  # A genuinely blank page is not an OCR failure.
        pdf.save(str(source))
    with pytest.raises(AppError) as error:
        ingest.extract_blocks(source, fmt="pdf", local_only=True)
    assert error.value.code == "LOCAL_OCR_REQUIRED"
    assert error.value.detail == {"pages_in_analyzed_pdf": [2]}
