"""Documents API — upload / list / get / pdf / export / rollback / history."""

from __future__ import annotations

import uuid
from typing import Literal, Optional

import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import ingest
from app.core.errors import AppError
from app.core.pdf_versioning import current_path, init_storage, path_for
from app.core.versioning import sha256_of_bytes
from app.db.models import Document, EditHistory, StandardVersion
from app.db.session import get_db
from app.parsers.pdf_parser import parse_pdf
from app.schemas import DocumentOut, EditHistoryOut, RollbackIn


router = APIRouter(tags=["documents"])


_MAX_BATCH_SIZE = 20


def _resolve_standard_versions(
    standard_version_id: Optional[uuid.UUID],
    standard_version_ids: Optional[str],
    db: Session,
) -> tuple[Optional[uuid.UUID], list[uuid.UUID]]:
    """Resolve the multi-norm payload into a validated (primary, [all]) pair.

    `standard_version_id` (single, legacy) and `standard_version_ids`
    (comma-separated, v2 multi-norm) can be combined: every value listed
    is validated against the DB, the *first* one becomes the « primary »
    that stays in `Document.standard_version_id` for backward compat.
    """
    raw_ids: list[uuid.UUID] = []
    if standard_version_id is not None:
        raw_ids.append(standard_version_id)
    if standard_version_ids:
        for token in standard_version_ids.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                raw_ids.append(uuid.UUID(token))
            except ValueError as exc:
                raise AppError(
                    "STANDARD_VERSION_INVALID",
                    f"UUID de version de norme invalide : {token}",
                    status_code=400,
                ) from exc

    # De-duplicate while preserving order.
    seen: set[uuid.UUID] = set()
    deduped: list[uuid.UUID] = []
    for vid in raw_ids:
        if vid in seen:
            continue
        seen.add(vid)
        deduped.append(vid)

    for vid in deduped:
        if db.get(StandardVersion, vid) is None:
            raise AppError(
                "STANDARD_VERSION_NOT_FOUND",
                "Version de norme introuvable",
                status_code=400,
            )
    primary = deduped[0] if deduped else None
    return primary, deduped


def _persist_pdf(
    pdf_bytes: bytes,
    display_name: str,
    target: str,
    db: Session,
    standard_version_id: Optional[uuid.UUID] = None,
    standard_version_ids: Optional[list[uuid.UUID]] = None,
) -> Document:
    """Persist a **PDF** (native or converted from Word) as a new `Document` row.

    The stored artifact is always the faithful PDF — page count and signature
    check run on it. `display_name` keeps the original upload name (incl. a
    `.doc/.docx` extension) for traceability.
    """
    sha = sha256_of_bytes(pdf_bytes)
    doc_id = uuid.uuid4()
    storage_dir_value = f"document_{doc_id.hex}"
    init_storage(storage_dir_value, pdf_bytes)

    try:
        opened = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise AppError("PDF_INVALID", "PDF illisible", status_code=400) from exc
    try:
        if _has_signature(opened):
            raise AppError(
                "PDF_HAS_SIGNATURE",
                "Les PDF signés numériquement ne peuvent pas être édités",
                status_code=400,
            )
        page_count = opened.page_count
    finally:
        opened.close()

    import json as _json

    document = Document(
        id=doc_id,
        original_filename=display_name,
        sha256=sha,
        storage_dir=storage_dir_value,
        page_count=page_count,
        target_unit_system=target,
        standard_version_id=standard_version_id,
        standard_version_ids=_json.dumps([str(v) for v in (standard_version_ids or [])]),
        status="uploaded",
        current_version=0,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def _ingest_and_persist(
    name: str,
    data: bytes,
    target: str,
    db: Session,
    standard_version_id: Optional[uuid.UUID] = None,
    standard_version_ids: Optional[list[uuid.UUID]] = None,
) -> Document:
    """Normalize one supported file (.pdf/.doc/.docx) to a faithful PDF, persist it.

    `.doc/.docx` go through Word COM / LibreOffice conversion (may be slow) —
    this runs inside FastAPI's sync threadpool, off the async loop.
    """
    pdf_bytes, display_name = ingest.to_pdf_bytes(name, data)
    return _persist_pdf(
        pdf_bytes, display_name, target, db,
        standard_version_id=standard_version_id,
        standard_version_ids=standard_version_ids,
    )


@router.post("/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    target: Literal["metric", "imperial", "auto", "none"] = Query(default="none"),
    standard_version_id: Optional[uuid.UUID] = Query(default=None),
    standard_version_ids: Optional[str] = Query(
        default=None,
        description="Comma-separated UUIDs of standard versions to apply at analyse",
    ),
    db: Session = Depends(get_db),
) -> Document:
    primary, all_ids = _resolve_standard_versions(
        standard_version_id, standard_version_ids, db
    )
    name = file.filename or "upload"
    if name.lower().endswith(".zip"):
        raise AppError(
            "USE_BATCH",
            "Les archives .zip doivent etre envoyees via /documents/batch",
            status_code=400,
        )
    data = file.file.read()
    return _ingest_and_persist(
        name, data, target, db,
        standard_version_id=primary,
        standard_version_ids=all_ids,
    )


@router.post("/documents/batch")
def upload_documents_batch(
    files: list[UploadFile] = File(...),
    target: Literal["metric", "imperial", "auto", "none"] = Query(default="none"),
    standard_version_id: Optional[uuid.UUID] = Query(default=None),
    standard_version_ids: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Upload many files at once — `.pdf/.doc/.docx` and `.zip` archives. Zips are
    expanded, Word files converted to a faithful PDF. Per-file failures are
    returned in `failed` rather than rolling everything back — partial success
    is intended. `ignored` lists archive members with an unsupported extension."""
    if not files:
        raise AppError("UPLOAD_EMPTY", "Aucun fichier reçu", status_code=400)
    if len(files) > _MAX_BATCH_SIZE:
        raise AppError(
            "UPLOAD_BATCH_TOO_LARGE",
            f"Maximum {_MAX_BATCH_SIZE} fichiers par batch",
            status_code=400,
        )

    primary, all_ids = _resolve_standard_versions(
        standard_version_id, standard_version_ids, db
    )
    raw_items = [(f.filename or "upload", f.file.read()) for f in files]
    expanded, ignored = ingest.expand_uploads(raw_items)

    created: list[dict] = []
    failed: list[dict] = []
    for name, data in expanded:
        try:
            doc = _ingest_and_persist(
                name, data, target, db,
                standard_version_id=primary,
                standard_version_ids=all_ids,
            )
            created.append(DocumentOut.model_validate(doc).model_dump(mode="json"))
        except AppError as exc:
            failed.append({"filename": name, "code": exc.code, "message": exc.message})
        except Exception as exc:  # noqa: BLE001
            failed.append({"filename": name, "code": "INTERNAL_ERROR", "message": str(exc)})

    status = 201 if not failed else (207 if created else 400)
    return JSONResponse(
        status_code=status,
        content={"created": created, "failed": failed, "ignored": ignored},
    )


def _has_signature(doc: fitz.Document) -> bool:
    try:
        if hasattr(doc, "get_signatures"):
            return bool(doc.get_signatures())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return False
    return False


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    return doc


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    storage_dir = doc.storage_dir
    db.delete(doc)
    db.commit()
    # Cleanup the snapshot folder on disk too — otherwise an admin
    # « Tout supprimer » leaves orphan `document_*/v0.pdf` files
    # cluttering the data directory. Use the admin helper so the
    # Windows read-only bit on v0.pdf is handled correctly.
    from app.api.admin import _remove_storage_dir as _rm_storage

    _rm_storage(storage_dir)


@router.get("/documents/{document_id}/pdf")
def get_pdf(
    document_id: uuid.UUID,
    version: str = Query(default="current"),
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)

    if version == "current":
        target = current_path(doc.storage_dir, doc.current_version)
    elif version == "original":
        target = path_for(doc.storage_dir, 0)
    else:
        try:
            n = int(version)
        except ValueError as exc:
            raise AppError("VERSION_INVALID", "Version invalide", status_code=400) from exc
        target = path_for(doc.storage_dir, n)

    if not target.is_file():
        raise AppError("PDF_VERSION_MISSING", "Snapshot absent", status_code=404)

    return FileResponse(
        target,
        media_type="application/pdf",
        filename=doc.original_filename,
    )


@router.get("/documents/{document_id}/pages/{page_number}.png")
def render_page_png(
    document_id: uuid.UUID,
    page_number: int,
    dpi: int = Query(default=120, ge=72, le=300),
    db: Session = Depends(get_db),
) -> Response:
    """Rasterize one page of the current PDF to PNG.

    Used by the preview HTML viewer to overlay suggestion bboxes over a
    bitmap rendering of the page (no PDF.js dependency).
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    if page_number < 1 or page_number > doc.page_count:
        raise AppError(
            "PDF_PAGE_OUT_OF_RANGE",
            f"Page {page_number} hors limites (1..{doc.page_count})",
            status_code=400,
        )

    src = current_path(doc.storage_dir, doc.current_version)
    pdf = fitz.open(src)
    try:
        page = pdf.load_page(page_number - 1)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        png_bytes = pix.tobytes("png")
    finally:
        pdf.close()

    etag = f'"{doc.id.hex}:{doc.current_version}:{page_number}:{dpi}"'
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=60", "ETag": etag},
    )


@router.get("/documents/{document_id}/export")
def export_pdf(document_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    target = current_path(doc.storage_dir, doc.current_version)
    return FileResponse(
        target,
        media_type="application/pdf",
        filename=doc.original_filename,
        headers={"Content-Disposition": f'attachment; filename="{doc.original_filename}"'},
    )


@router.get("/documents/{document_id}/commented.pdf")
def export_commented_pdf(document_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """PDF **commente** : le PDF fidele + les anomalies retenues (non rejetees)
    estampillees en annotations, plus une page-sommaire. C'est le livrable sur
    lequel le relecteur s'appuie pour corriger son document Word."""
    from app.core.pdf_annotate import build_commented_pdf
    from app.db.models import Suggestion as SuggestionModel

    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    src = current_path(doc.storage_dir, doc.current_version)
    if not src.is_file():
        raise AppError("PDF_VERSION_MISSING", "PDF courant absent", status_code=500)

    suggestions = list(
        db.scalars(
            select(SuggestionModel)
            .where(
                SuggestionModel.document_id == document_id,
                SuggestionModel.status != "rejected",
            )
            .order_by(SuggestionModel.page, SuggestionModel.span_index)
        )
    )
    pdf_bytes = build_commented_pdf(str(src), suggestions)

    stem = doc.original_filename.rsplit(".", 1)[0]
    out_name = f"{stem}_commente.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )


@router.post("/documents/{document_id}/rollback", response_model=DocumentOut)
def rollback_document(
    document_id: uuid.UUID,
    body: RollbackIn,
    db: Session = Depends(get_db),
) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)

    target = path_for(doc.storage_dir, body.target_version)
    if not target.is_file():
        raise AppError(
            "PDF_VERSION_MISSING",
            f"Version {body.target_version} introuvable",
            status_code=404,
        )

    previous = doc.current_version
    doc.current_version = body.target_version
    db.add(
        EditHistory(
            document_id=doc.id,
            suggestion_id=None,
            version_before=previous,
            version_after=body.target_version,
            snapshot_path=str(target),
            diff_summary='{"action": "rollback"}',
            rolled_back=True,
        )
    )
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents/{document_id}/history", response_model=list[EditHistoryOut])
def get_history(document_id: uuid.UUID, db: Session = Depends(get_db)) -> list[EditHistory]:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    stmt = (
        select(EditHistory)
        .where(EditHistory.document_id == document_id)
        .order_by(EditHistory.applied_at.desc())
    )
    return list(db.scalars(stmt))


@router.get("/documents/{document_id}/suggestions")
def list_document_suggestions(
    document_id: uuid.UUID,
    status: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    rule_kind: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Filtered suggestion listing scoped to one document.

    Mirrors GET /suggestions?document_id=… but is the canonical front URL.
    """
    from app.db.models import Suggestion as SuggestionModel
    from app.schemas import SuggestionOut

    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)

    stmt = select(SuggestionModel).where(SuggestionModel.document_id == document_id)
    if status:
        stmt = stmt.where(SuggestionModel.status == status)
    if severity:
        stmt = stmt.where(SuggestionModel.severity == severity)
    if rule_kind:
        stmt = stmt.where(SuggestionModel.rule_kind == rule_kind)

    rows = list(db.scalars(stmt.order_by(
        SuggestionModel.page,
        SuggestionModel.span_index,
        SuggestionModel.created_at,
        SuggestionModel.id,
    )))
    return [SuggestionOut.model_validate(r).model_dump(mode="json") for r in rows]


# Parses suggestions endpoint inline to avoid a circular import.
