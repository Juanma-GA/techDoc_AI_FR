"""Category 2 performance guarantees, using generated fixtures only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pymupdf as fitz
import pytest
from sqlalchemy import inspect, select

from app.core import s1000d_schema, wizard
from app.core import s1000d_serializer as serializer
from app.core.ir import IRNode
from app.core.resolver import resolve
from app.core.structure_heuristics import detect_refs
from app.db.models import Document
from app.db.session import SessionLocal


def _root(with_refs: bool = False) -> IRNode:
    root = IRNode(
        id="root",
        kind="section",
        children=[
            IRNode(
                id="section",
                kind="section",
                text="1 Description",
                level=1,
                children=[
                    IRNode(
                        id="paragraph",
                        kind="paragraph",
                        text="See Figure 1.",
                        refs=detect_refs("See Figure 1.") if with_refs else None,
                    ),
                    IRNode(id="figure", kind="figure", text="Figure 1 Pump", icn="figure.jpg"),
                ],
            ),
        ],
    )
    resolve(root)
    return root


@pytest.mark.parametrize("with_refs", [False, True])
def test_cached_xml_matches_uncached_xml_byte_for_byte(with_refs) -> None:
    root = _root(with_refs)
    metadata = {"dm_type": "descriptive", "issue": "4.2", "dmc": "DMC-PUMP-A-00-00-00-00A-040A-D"}
    index = serializer.build_reference_index([("dm", root, metadata)])
    options = dict(
        issue="4.2",
        dm_type="descriptive",
        dm_metadata=metadata,
        reference_dm_id="dm",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    cached = serializer.serialize(root, reference_index=index, **options)
    uncached = serializer.serialize(root, reference_index=dict(index), **options)
    assert cached.encode("utf-8") == uncached.encode("utf-8")
    if with_refs:
        assert "<internalRef " in cached


def test_content_is_built_once_and_ir_changes_invalidate_cache(monkeypatch) -> None:
    root = _root()
    original = serializer._build_content
    builds = 0

    def build(*args, **kwargs):
        nonlocal builds
        builds += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(serializer, "_build_content", build)
    index = serializer.build_reference_index([("dm", root, {"dm_type": "descriptive"})])
    serializer.serialize(
        root, issue="4.2", dm_type="descriptive", reference_index=index, reference_dm_id="dm"
    )
    assert builds == 1
    root.children[0].children[0].text = "Changed source."
    xml = serializer.serialize(
        root, issue="4.2", dm_type="descriptive", reference_index=index, reference_dm_id="dm"
    )
    assert builds == 2
    assert "Changed source." in xml


def test_cached_cross_dm_references_match_uncached_xml() -> None:
    source = _root()
    paragraph = source.children[0].children[0]
    paragraph.text = "See Figure 2."
    paragraph.refs = detect_refs(paragraph.text)
    target = _root()
    target.children[0].children[1].text = "Figure 2 Pump"
    documents = [
        ("source", source, {"dm_type": "descriptive", "dmc": "DMC-PUMP-A-00-00-00-00A-040A-D"}),
        ("target", target, {"dm_type": "descriptive", "dmc": "DMC-PUMP-A-00-00-00-00A-041A-D"}),
    ]
    index = serializer.build_reference_index(documents)
    options = dict(
        issue="4.2",
        dm_type="descriptive",
        reference_dm_id="source",
        dm_metadata=documents[0][2],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    cached = serializer.serialize(source, reference_index=index, **options)
    uncached = serializer.serialize(source, reference_index=dict(index), **options)
    assert cached == uncached
    assert "referredFragment=" in cached


def test_schema_is_compiled_once_across_eight_threads(monkeypatch) -> None:
    xml = serializer.serialize(_root(), issue="4.2", dm_type="descriptive")
    monkeypatch.setattr(s1000d_schema, "_SCHEMA_CACHE", {})
    original = s1000d_schema.etree.XMLSchema
    compiled = 0

    def compile_schema(document):
        nonlocal compiled
        compiled += 1
        return original(document)

    monkeypatch.setattr(s1000d_schema.etree, "XMLSchema", compile_schema)

    def validate(worker):
        for iteration in range(20):
            invalid = (worker + iteration) % 2 == 0
            content = xml.replace("</content>", "<invalid/></content>") if invalid else xml
            violations = s1000d_schema.validate_xsd(
                content,
                "4.2",
                dm_type="descriptive",
                allow_internal_dtd=True,
            )
            assert bool(violations) is invalid

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(validate, range(8)))
    assert compiled == 1


def test_document_json_columns_are_loaded_only_on_access(client, pdf_bytes) -> None:
    uploaded = client.post("/api/v1/documents", files={"file": ("source.pdf", pdf_bytes)})
    assert uploaded.status_code == 201
    with SessionLocal() as db:
        document = db.scalar(select(Document))
        heavy = {"ir_json", "dms_json", "dms_history_json", "dmrl_json", "preliminary_review_json"}
        assert heavy <= inspect(document).unloaded
        assert document.ir_json is None
        assert "ir_json" not in inspect(document).unloaded


def _generated(client, data: bytes) -> tuple[str, dict]:
    uploaded = client.post("/api/v1/documents", files={"file": ("source.pdf", data)})
    assert uploaded.status_code == 201, uploaded.text
    doc_id = uploaded.json()["id"]
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/start", json={"cut_pdf": False})
    assert response.status_code == 200, response.text
    state = response.json()
    for _ in range(4):
        if state["step"] == "generate":
            break
        response = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
        assert response.status_code == 200, response.text
        state = response.json()
    assert state["step"] == "generate"
    return doc_id, state


def test_dm_get_is_read_only_and_reuses_stored_xml(client, pdf_bytes_image, monkeypatch) -> None:
    doc_id, state = _generated(client, pdf_bytes_image)
    dm_id = state["dms"][0]["dm_id"]
    with SessionLocal() as db:
        document = db.get(Document, doc_id)
        before = (document.dms_json, document.status, document.ir_json)

    def fail_render(*_args, **_kwargs):
        raise AssertionError("A current persisted XML must not be regenerated.")

    monkeypatch.setattr(wizard, "render_dm", fail_render)
    response = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{dm_id}/xml")
    assert response.status_code == 200, response.text
    assert response.headers["etag"]
    with SessionLocal() as db:
        document = db.get(Document, doc_id)
        assert (document.dms_json, document.status, document.ir_json) == before


def test_server_validation_uses_stored_dms_and_checks_selection(client, pdf_bytes_image) -> None:
    doc_id, state = _generated(client, pdf_bytes_image)
    dm_id = state["dms"][0]["dm_id"]
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/validate", json={"dm_ids": [dm_id]})
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["dm_id"] == dm_id
    assert "status" in response.json()["results"][0]
    missing = client.post(f"/api/v1/documents/{doc_id}/wizard/validate", json={"dm_ids": ["unknown"]})
    assert missing.status_code == 404
    invalid = client.post(f"/api/v1/documents/{doc_id}/wizard/validate", json={"dm_ids": "wrong"})
    assert invalid.status_code == 422


def test_preview_is_rendered_once_and_deleted_with_document(client, pdf_bytes_image, monkeypatch) -> None:
    from app.core import pdf_cut

    doc_id, _state = _generated(client, pdf_bytes_image)
    original = pdf_cut.preview_page
    calls = 0

    def preview(*args):
        nonlocal calls
        calls += 1
        return original(*args)

    monkeypatch.setattr(pdf_cut, "preview_page", preview)
    first = client.get(f"/api/v1/documents/{doc_id}/pdf-cut/preview/1")
    second = client.get(f"/api/v1/documents/{doc_id}/pdf-cut/preview/1")
    assert first.content == second.content
    assert calls == 1
    assert first.headers["etag"] == second.headers["etag"]
    assert first.headers["cache-control"] == "private, max-age=3600"
    with SessionLocal() as db:
        directory = pdf_cut.previews_dir(db.get(Document, doc_id))
    assert directory.exists()
    assert (
        client.delete(
            f"/api/v1/documents/{doc_id}?confirm_token=confirmed-token",
        ).status_code
        == 200
    )
    assert not directory.exists()


def test_pdf_table_detection_is_not_repeated_for_illustrations(client, pdf_bytes_image, monkeypatch) -> None:
    original = fitz.Page.find_tables
    calls = 0

    def tables(page, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(page, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "find_tables", tables)
    _generated(client, pdf_bytes_image)
    assert calls == 1


def test_uncut_restart_uses_original_pdf_for_both_parse_and_images(client) -> None:
    with fitz.open() as pdf:
        for page in range(3):
            pdf.new_page().insert_text((72, 72), f"Section {page + 1} with searchable source content.")
        data = pdf.tobytes()
    uploaded = client.post("/api/v1/documents", files={"file": ("source.pdf", data)})
    doc_id = uploaded.json()["id"]
    assert (
        client.post(
            f"/api/v1/documents/{doc_id}/pdf-cut/confirm", json={"start_page": 2, "end_page": 2}
        ).status_code
        == 200
    )
    response = client.post(f"/api/v1/documents/{doc_id}/wizard/start", json={"cut_pdf": False})
    assert response.status_code == 200, response.text
    assert response.json()["illustration_errors"] == 0


def test_zip_temporary_file_is_removed_after_response(client, pdf_bytes_image) -> None:
    import io
    import zipfile

    doc_id, _state = _generated(client, pdf_bytes_image)
    with SessionLocal() as db:
        directory = Path(db.get(Document, doc_id).storage_path).parent
        before = set(directory.glob("*.zip"))
        xml_before = db.get(Document, doc_id).dms_json
    response = client.get(f"/api/v1/documents/{doc_id}/wizard/zip?image_format=png")
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert any(name.endswith(".xml") for name in archive.namelist())
        assert any(name.endswith(".png") for name in archive.namelist())
    assert set(directory.glob("*.zip")) == before
    with SessionLocal() as db:
        assert db.get(Document, doc_id).dms_json == xml_before


def test_demo_mode_is_read_once_and_cache_updates_only_after_commit(monkeypatch) -> None:
    from app.core import demo_mode

    demo_mode.reset_demo_cache()
    original = demo_mode.get_demo_enabled
    reads = 0

    def read(db):
        nonlocal reads
        reads += 1
        return original(db)

    monkeypatch.setattr(demo_mode, "get_demo_enabled", read)
    assert demo_mode.current_demo_enabled() is False
    assert demo_mode.current_demo_enabled() is False
    assert reads == 1
    with SessionLocal() as db:
        demo_mode.set_demo_enabled(db, True)
    assert demo_mode.current_demo_enabled() is True
    with SessionLocal() as db:

        def fail_commit():
            raise RuntimeError("Synthetic commit failure")

        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="Synthetic"):
            demo_mode.set_demo_enabled(db, False)
    assert demo_mode.current_demo_enabled() is True


def test_original_zip_images_are_streamed_without_decoding_or_eager_reads(tmp_path, monkeypatch) -> None:
    import io
    import zipfile

    from app.core import wizard_zip_export

    path = tmp_path / "source.jpg"
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 32, 24))
    pixmap.clear_with(180)
    original = pixmap.tobytes("jpg")
    path.write_bytes(original)

    def fail_decode(*_args, **_kwargs):
        raise AssertionError("Original images must not be decoded or eagerly read.")

    monkeypatch.setattr(fitz, "open", fail_decode)
    monkeypatch.setattr(Path, "read_bytes", fail_decode)
    exports, name_map = wizard_zip_export.prepare_zip_images(
        [path],
        pictogram_names=set(),
        max_dimension=None,
        image_format="original",
    )
    assert name_map == {}
    assert not hasattr(exports[0], "content")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        exports[0].write_to(archive)
    with zipfile.ZipFile(buffer) as archive:
        assert archive.read(exports[0].archive_path) == original
