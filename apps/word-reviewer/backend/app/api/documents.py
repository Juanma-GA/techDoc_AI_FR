"""Routes /api/v1/documents - upload (single/multi/zip), liste, export.

Upload : 1..N fichiers ; un .zip est extrait (recursif) en ses .docx. Les
documents d'un meme upload forment un `Batch`. Export : un .docx corrige, ou un
.zip pour plusieurs documents.
"""

from __future__ import annotations

import io
import json
import logging
import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import docx_versioning as ver
from app.core.doc_convert import doc_to_docx_bytes
from app.core.docx_zones import recognize_zones
from app.core.errors import AppError
from app.core.uploads import extract_uploads
from app.db.models import Batch, Document, StandardVersion, Suggestion
from app.db.session import get_db
from app.parsers.docx_parser import parse_docx
from app.schemas import (
    DocumentOut,
    DocumentViewOut,
    ExportZipRequest,
    SuggestionOut,
    UploadResult,
    ViewBlock,
)


log = logging.getLogger("word_reviewer.documents")

router = APIRouter(prefix="/documents", tags=["documents"])


def _ids_list(raw: str) -> list[uuid.UUID]:
    try:
        return [uuid.UUID(x) for x in json.loads(raw or "[]")]
    except (ValueError, TypeError):
        return []


def doc_out(doc: Document, total: int = 0, open_: int = 0) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        original_filename=doc.original_filename,
        status=doc.status,
        block_count=doc.block_count,
        current_version=doc.current_version,
        batch_id=doc.batch_id,
        standard_version_ids=_ids_list(doc.standard_version_ids),
        created_at=doc.created_at,
        findings_total=total,
        findings_open=open_,
    )


def _default_version_ids(db: Session) -> list[str]:
    ids = db.scalars(select(StandardVersion.id).where(StandardVersion.builtin.is_(True))).all()
    return [str(i) for i in ids]


@router.post("", response_model=UploadResult)
async def upload(files: list[UploadFile], db: Session = Depends(get_db)) -> UploadResult:
    if not files:
        raise AppError("NO_FILE", "Aucun fichier fourni.", 400)
    items: list[tuple[str, bytes]] = []
    for f in files:
        items.append((f.filename or "upload", await f.read()))
    docx_files, ignored = extract_uploads(items)

    default_ids = json.dumps(_default_version_ids(db))
    batch = Batch(label=docx_files[0][0] if len(docx_files) == 1 else f"{len(docx_files)} fichiers")
    db.add(batch)
    db.flush()

    created: list[Document] = []
    for name, data in docx_files:
        # .doc legacy -> conversion en .docx (LibreOffice / Word COM).
        if name.lower().endswith(".doc"):
            data = doc_to_docx_bytes(data)
            name = name[:-4] + ".docx"
        doc_id = uuid.uuid4()
        storage_dir = ver.doc_dir_name(doc_id.hex)
        ver.write_version(storage_dir, 0, data)
        try:
            parsed = parse_docx(ver.version_path(storage_dir, 0))
            block_count = parsed.block_count
        except Exception as exc:  # noqa: BLE001
            log.warning("docx parse failed at upload: %s", name)
            raise AppError("BAD_DOCX", f"{name} n'est pas un .docx lisible.", 400) from exc
        doc = Document(
            id=doc_id,
            original_filename=name,
            sha256=ver.sha256_bytes(data),
            storage_dir=storage_dir,
            block_count=block_count,
            batch_id=batch.id,
            standard_version_ids=default_ids,
            status="uploaded",
            current_version=0,
        )
        db.add(doc)
        created.append(doc)
    db.flush()  # peuple created_at / defaults avant serialisation
    out_docs = [doc_out(d) for d in created]
    db.commit()
    return UploadResult(batch_id=batch.id, documents=out_docs, ignored=ignored)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    batch_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[DocumentOut]:
    stmt = select(Document).order_by(Document.created_at.desc())
    if batch_id is not None:
        stmt = stmt.where(Document.batch_id == batch_id)
    docs = list(db.scalars(stmt))
    # Compteurs d'anomalies par document (1 requete groupee).
    from sqlalchemy import case, func

    rows = db.execute(
        select(
            Suggestion.document_id,
            func.count(Suggestion.id),
            func.sum(case((Suggestion.status == "open", 1), else_=0)),
        ).group_by(Suggestion.document_id)
    ).all()
    counts = {doc_id: (int(total), int(open_ or 0)) for doc_id, total, open_ in rows}
    return [doc_out(d, *counts.get(d.id, (0, 0))) for d in docs]


def _get_doc(db: Session, document_id: uuid.UUID) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("NOT_FOUND", "Document introuvable.", 404)
    return doc


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentOut:
    return doc_out(_get_doc(db, document_id))


@router.delete("/{document_id}")
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, bool]:
    doc = _get_doc(db, document_id)
    storage_dir = doc.storage_dir
    db.delete(doc)  # cascade -> suggestions, runs, edit_history
    db.commit()
    shutil.rmtree(ver.doc_dir(storage_dir), ignore_errors=True)  # versions sur disque
    return {"deleted": True}


@router.get("/{document_id}/view", response_model=DocumentViewOut)
def document_view(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentViewOut:
    """Rendu structure de la version courante (pour la vue HTML + surlignage)."""
    doc = _get_doc(db, document_id)
    try:
        parsed = recognize_zones(parse_docx(ver.version_path(doc.storage_dir, doc.current_version)))
    except Exception as exc:  # noqa: BLE001
        raise AppError("BAD_DOCX", "Document illisible pour la vue.", 400) from exc
    blocks = [
        ViewBlock(
            target_id=b.target_id,
            kind=b.kind,
            zone=b.zone,
            semantic_zone=b.semantic_zone or "",
            heading_level=b.heading_level,
            text=b.text,
            table_id=b.table_id,
            row=b.row,
            col=b.col,
        )
        for b in parsed.blocks
    ]
    return DocumentViewOut(
        id=doc.id,
        original_filename=doc.original_filename,
        current_version=doc.current_version,
        blocks=blocks,
    )


@router.get("/{document_id}/suggestions", response_model=list[SuggestionOut])
def list_suggestions(document_id: uuid.UUID, db: Session = Depends(get_db)) -> list[SuggestionOut]:
    _get_doc(db, document_id)
    stmt = (
        select(Suggestion)
        .where(Suggestion.document_id == document_id)
        .order_by(Suggestion.block_index, Suggestion.char_start)
    )
    return [SuggestionOut.model_validate(s) for s in db.scalars(stmt)]


def _current_bytes(doc: Document) -> bytes:
    try:
        return ver.read_version(doc.storage_dir, doc.current_version)
    except FileNotFoundError as exc:
        raise AppError("NOT_FOUND", "Fichier du document introuvable.", 404) from exc


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/{document_id}/export")
def export_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    doc = _get_doc(db, document_id)
    data = _current_bytes(doc)
    headers = {"Content-Disposition": f'attachment; filename="{Path(doc.original_filename).name}"'}
    return StreamingResponse(io.BytesIO(data), media_type=_DOCX_MIME, headers=headers)


@router.post("/export-zip")
def export_zip(payload: ExportZipRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    if not payload.document_ids:
        raise AppError("NO_SELECTION", "Aucun document selectionne.", 400)
    buf = io.BytesIO()
    used: dict[str, int] = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc_id in payload.document_ids:
            doc = db.get(Document, doc_id)
            if doc is None:
                continue
            name = Path(doc.original_filename).name
            count = used.get(name, 0)
            used[name] = count + 1
            arc = name if count == 0 else f"{Path(name).stem}_{count}{Path(name).suffix}"
            zf.writestr(arc, _current_bytes(doc))
    buf.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="word-reviewer-export.zip"'}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)
