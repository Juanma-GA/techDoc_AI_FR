import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.config import settings
from app.db.models import Document
from app.db.session import SessionLocal


def _upload(client, raw, **options):
    return client.post(
        "/api/v1/documents",
        files={"file": ("synthetic.pdf", raw)},
        data={"s1000d_issue": "4.2", "context_hint": "mixed", **options},
    )


def test_identical_document_reuses_id_but_issue_and_context_remain_distinct(client, pdf_bytes) -> None:
    first = _upload(client, pdf_bytes)
    second = _upload(client, pdf_bytes)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.headers["x-reused"] == "true"
    assert len(client.get("/api/v1/documents").json()) == 1
    assert _upload(client, pdf_bytes, s1000d_issue="4.1").json()["id"] != first.json()["id"]
    assert _upload(client, pdf_bytes, context_hint="procedural").json()["id"] != first.json()["id"]
    with SessionLocal() as db:
        doc = db.get(Document, first.json()["id"])
        assert doc.sha256 == hashlib.sha256(pdf_bytes).hexdigest()


def test_parallel_identical_uploads_do_not_create_duplicates(client, pdf_bytes) -> None:
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _index: _upload(client, pdf_bytes), range(4)))
    assert all(result.status_code == 201 for result in results)
    assert len({result.json()["id"] for result in results}) == 1
    assert len(client.get("/api/v1/documents").json()) == 1


def test_last_saved_legacy_document_is_hashed_lazily_and_reused(client, pdf_bytes) -> None:
    first = _upload(client, pdf_bytes)
    with SessionLocal() as db:
        db.get(Document, first.json()["id"]).sha256 = None
        db.commit()
    reused = _upload(client, pdf_bytes)
    assert reused.json()["id"] == first.json()["id"]
    assert reused.headers["x-reused"] == "true"
    assert len(client.get("/api/v1/documents").json()) == 1


def test_same_document_with_different_brex_is_not_reused(client, pdf_bytes, brex_xml) -> None:
    profile = client.post(
        "/api/v1/brex",
        files={"file": ("rules.xml", brex_xml.encode())},
        data={"name": "Synthetic", "s1000d_issue": "4.2"},
    ).json()
    first = _upload(client, pdf_bytes)
    other = _upload(client, pdf_bytes, brex_id=profile["id"])
    assert first.json()["id"] != other.json()["id"]
    assert "x-reused" not in other.headers


def test_identical_resource_is_not_rewritten_or_parsed_twice(client, pdf_bytes, monkeypatch) -> None:
    from app.api import resources

    doc_id = _upload(client, pdf_bytes).json()["id"]
    raw = json.dumps([{"DMC": "DMC-PUMP-A-00-00-00-00A-040A-D", "Titre": "Synthetic"}]).encode()
    path = f"/api/v1/documents/{doc_id}/resources/dmrl"
    assert client.post(path, files={"file": ("dmrl.json", raw)}).status_code == 200
    with SessionLocal() as db:
        saved = Path(db.get(Document, doc_id).dmrl_path)
        stamp = saved.stat().st_mtime_ns

    def fail_parse(*_args, **_kwargs):
        raise AssertionError("An unchanged resource must not be parsed twice.")

    monkeypatch.setattr(resources.dmrl_mod, "load_dmrl", fail_parse)
    response = client.post(path, files={"file": ("same.json", raw)})
    assert response.status_code == 200, response.text
    assert response.headers["x-reused"] == "true"
    assert response.json() == {"kind": "dmrl", "count": 1}
    assert saved.stat().st_mtime_ns == stamp


def test_invalid_resource_replacement_preserves_previous_file(client, pdf_bytes) -> None:
    doc_id = _upload(client, pdf_bytes).json()["id"]
    raw = b'[{"DMC":"DMC-PUMP-A-00-00-00-00A-040A-D","Titre":"Synthetic"}]'
    endpoint = f"/api/v1/documents/{doc_id}/resources/dmrl"
    assert client.post(endpoint, files={"file": ("dmrl.json", raw)}).status_code == 200
    with SessionLocal() as db:
        path = Path(db.get(Document, doc_id).dmrl_path)
    failed = client.post(endpoint, files={"file": ("bad.json", b"invalid JSON")})
    assert failed.status_code == 422
    assert path.read_bytes() == raw
    assert not list(path.parent.glob(".upload-*"))


def test_removing_resource_clears_mapping_and_hash_without_removing_document(client, pdf_bytes) -> None:
    doc_id = _upload(client, pdf_bytes).json()["id"]
    endpoint = f"/api/v1/documents/{doc_id}/resources/dm_header"
    assert (
        client.post(
            endpoint, files={"file": ("header.json", b'{"security":{"securityClassification":"04"}}')}
        ).status_code
        == 200
    )
    with SessionLocal() as db:
        path = Path(db.get(Document, doc_id).dm_header_path)
    removed = client.delete(endpoint)
    assert removed.status_code == 200
    assert not path.exists()
    assert "dm_header" not in client.get("/api/v1/migration-inputs").json()["files"]
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        assert doc.dm_header_json is None
        assert "dm_header" not in json.loads(doc.resource_sha256_json)


def test_validation_enforces_file_count_and_aggregate_size(client, monkeypatch) -> None:
    too_many = client.post(
        "/api/v1/validation/dms",
        files=[("files", (f"dm-{index}.xml", b"<dmodule/>", "application/xml")) for index in range(21)],
    )
    assert too_many.status_code == 413
    assert too_many.json()["code"] == "VALIDATION_TOO_MANY_FILES"
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    data = b" " * 600_000 + b"<dmodule/>"
    too_large = client.post(
        "/api/v1/validation/dms",
        files=[("files", (f"dm-{index}.xml", data, "application/xml")) for index in range(2)],
    )
    assert too_large.status_code == 413
    assert too_large.json()["code"] == "FILE_TOO_LARGE"


def test_thumbnail_is_small_and_cached(client, pdf_bytes_image, monkeypatch) -> None:
    import pymupdf as fitz

    from app.core import image_previews

    doc_id = _upload(client, pdf_bytes_image).json()["id"]
    client.post(f"/api/v1/documents/{doc_id}/wizard/start", json={"cut_pdf": False})
    names = client.get(f"/api/v1/documents/{doc_id}/wizard/images").json()
    url = f"/api/v1/documents/{doc_id}/wizard/images/{names[0]}/thumb?size=64"
    response = client.get(url)
    assert response.status_code == 200
    pixmap = fitz.Pixmap(response.content)
    assert max(pixmap.width, pixmap.height) <= 64

    def fail_render(*_args, **_kwargs):
        raise AssertionError("A cached thumbnail must not be rendered twice.")

    monkeypatch.setattr(image_previews.fitz, "open", fail_render)
    second = client.get(url)
    assert second.content == response.content
    assert second.headers["etag"] == response.headers["etag"]
