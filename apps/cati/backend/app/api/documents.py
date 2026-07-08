"""Routes /api/v1/documents - upload PDF plan de montage + extraction BOM.

Upload -> validation (PDF, taille) -> dedup sha256 -> stockage disque ->
extraction deterministe (filet LLM si active) -> persistance document + items.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Form, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.challenge import run_challenge
from app.core.errors import AppError
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled
from app.core.profiles import get_profile, pdf_map_of
from app.core.security import read_and_validate, safe_storage_join
from app.core.versioning import sha256_of_bytes
from app.db.models import CatiDocument, CatiItem
from app.db.session import get_db
from app.parsers.pdf_table import dumps_meta, extract_bom
from app.schemas import (
    ChallengeReport,
    DocumentOut,
    HeaderMeta,
    ItemOut,
    ItemsOut,
    UploadItemResult,
    UploadResultOut,
)

log = logging.getLogger("cati.documents")

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTS = {".pdf"}


# --- helpers ----------------------------------------------------------------


def _doc_dir(doc_id: str) -> Path:
    root = Path(settings.storage_dir)
    return safe_storage_join(root, "documents", f"doc_{doc_id}")


def _extraction_warnings(doc: CatiDocument) -> list[str]:
    try:
        meta = json.loads(doc.extraction_meta or "{}")
        w = meta.get("warnings")
        return list(w) if isinstance(w, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _challenge_report(doc: CatiDocument) -> ChallengeReport:
    try:
        raw = json.loads(doc.challenge or "{}")
    except (json.JSONDecodeError, TypeError):
        raw = {}
    if not raw:
        return ChallengeReport()
    try:
        return ChallengeReport(**raw)
    except (TypeError, ValueError):
        return ChallengeReport(status=str(raw.get("status", "none")))


def _document_out(db: Session, doc: CatiDocument) -> DocumentOut:
    item_count = db.scalar(
        select(func.count(CatiItem.id)).where(CatiItem.document_id == doc.id)
    ) or 0
    try:
        header_meta = HeaderMeta(**json.loads(doc.header_meta or "{}"))
    except (json.JSONDecodeError, TypeError):
        header_meta = HeaderMeta()
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        size=doc.size,
        page_count=doc.page_count,
        status=doc.status,
        extraction_method=doc.extraction_method,
        item_count=int(item_count),
        profile_id=doc.profile_id,
        header_meta=header_meta,
        warnings=_extraction_warnings(doc),
        challenge=_challenge_report(doc),
        error=doc.error,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
    )


def _current_items_payload(db: Session, doc_id: str) -> list[dict]:
    """Champs des items persistes (pour diffuser avec la relecture LLM)."""
    rows = db.scalars(
        select(CatiItem).where(CatiItem.document_id == doc_id).order_by(CatiItem.order_index)
    ).all()
    payload: list[dict] = []
    for r in rows:
        try:
            payload.append(json.loads(r.fields or "{}"))
        except (json.JSONDecodeError, TypeError):
            continue
    return payload


def _run_and_store_challenge(db: Session, doc: CatiDocument, mistral: MistralClient | None) -> None:
    """Controle LLM (relecture + diff) stocke sur le document. Best-effort."""
    try:
        report = run_challenge(doc.storage_path, _current_items_payload(db, doc.id), mistral)
    except Exception as e:  # noqa: BLE001 - controle non bloquant, jamais de 5xx
        log.warning("challenge failed for %s: %s", doc.id, e)
        report = {"status": "skipped", "reason": f"{type(e).__name__}", "summary": {}, "rows": []}
    doc.challenge = json.dumps(report, ensure_ascii=False)


def _item_out(item: CatiItem) -> ItemOut:
    try:
        fields = json.loads(item.fields or "{}")
    except (json.JSONDecodeError, TypeError):
        fields = {}
    return ItemOut(
        id=item.id,
        order_index=item.order_index,
        source_page=item.source_page,
        fields=fields,
        included=item.included,
        edited=item.edited,
    )


def _get_doc(db: Session, doc_id: str) -> CatiDocument:
    doc = db.get(CatiDocument, doc_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable.", status_code=404)
    return doc


def _mistral_or_none(db: Session) -> MistralClient | None:
    """Garde-fou standard : LLM OFF -> extraction 100% deterministe (jamais 5xx)."""
    if not get_llm_enabled(db):
        return None
    try:
        return MistralClient.from_db(db)
    except MistralError:
        return None


_ITEM_FIELDS = (
    "fig", "figreflink", "aplomb", "description", "matiere",
    "ref_client", "ref_interne", "ref_fournisseur", "qty", "symbole",
)


def _persist_items(db: Session, doc: CatiDocument, items: list[dict]) -> None:
    db.query(CatiItem).filter(CatiItem.document_id == doc.id).delete()
    for it in items:
        fields = {k: it.get(k, "") for k in _ITEM_FIELDS}
        db.add(
            CatiItem(
                document_id=doc.id,
                order_index=int(it.get("order_index", 0)),
                source_page=it.get("source_page"),
                fields=json.dumps(fields, ensure_ascii=False),
                included=True,
                edited=False,
            )
        )


# --- routes -----------------------------------------------------------------


@router.post("", response_model=UploadResultOut)
def upload_documents(
    files: list[UploadFile],
    profile_id: str | None = Form(None),
    db: Session = Depends(get_db),
) -> UploadResultOut:
    mistral = _mistral_or_none(db)
    llm_enabled = mistral is not None
    profile = get_profile(db, profile_id)
    pdf_map = pdf_map_of(profile)
    results: list[UploadItemResult] = []

    for upload in files:
        try:
            raw, safe_name, ext = read_and_validate(
                upload,
                max_size=settings.max_upload_size_bytes,
                allowed_exts=ALLOWED_EXTS,
            )
        except AppError as e:
            results.append(UploadItemResult(filename=upload.filename or "", status="error", error=e.message))
            continue

        digest = sha256_of_bytes(raw)
        existing = db.scalar(select(CatiDocument).where(CatiDocument.sha256 == digest))
        if existing is not None:
            results.append(
                UploadItemResult(
                    filename=safe_name, document_id=existing.id, status="duplicate",
                    item_count=db.scalar(
                        select(func.count(CatiItem.id)).where(CatiItem.document_id == existing.id)
                    ) or 0,
                )
            )
            continue

        doc = CatiDocument(
            filename=safe_name, mime_type="application/pdf", size=len(raw), sha256=digest,
            profile_id=(profile.id if profile else None),
        )
        db.add(doc)
        db.flush()  # obtient doc.id

        target_dir = _doc_dir(doc.id)
        target_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = target_dir / safe_name
        pdf_path.write_bytes(raw)
        doc.storage_path = str(pdf_path)

        try:
            res = extract_bom(str(pdf_path), mistral=mistral, llm_enabled=llm_enabled, pdf_map=pdf_map)
        except Exception as e:  # noqa: BLE001 - extraction defaillante -> doc en erreur, pas de 5xx
            log.exception("extraction failed for %s", safe_name)
            doc.status = "error"
            doc.error = f"{type(e).__name__}: {e}"
            db.commit()
            results.append(UploadItemResult(filename=safe_name, document_id=doc.id, status="error", error=doc.error))
            continue

        doc.page_count = int(res["page_count"])
        doc.extraction_method = res["method"]
        doc.status = "extracted"
        doc.extraction_meta = dumps_meta(res["warnings"])
        _persist_items(db, doc, res["items"])
        db.flush()
        # Controle LLM systematique quand le LLM est disponible (sinon skipped).
        _run_and_store_challenge(db, doc, mistral)
        db.commit()

        results.append(
            UploadItemResult(
                filename=safe_name, document_id=doc.id, status="created", item_count=len(res["items"])
            )
        )

    return UploadResultOut(results=results)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentOut]:
    docs = db.scalars(select(CatiDocument).order_by(CatiDocument.created_at.desc())).all()
    return [_document_out(db, d) for d in docs]


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, db: Session = Depends(get_db)) -> DocumentOut:
    return _document_out(db, _get_doc(db, doc_id))


@router.delete("/{doc_id}", response_model=DocumentOut)
def delete_document(doc_id: str, db: Session = Depends(get_db)) -> DocumentOut:
    doc = _get_doc(db, doc_id)
    out = _document_out(db, doc)
    try:
        shutil.rmtree(_doc_dir(doc_id), ignore_errors=True)
    except OSError:
        log.warning("could not remove storage dir for %s", doc_id)
    db.delete(doc)
    db.commit()
    return out


@router.put("/{doc_id}/header-meta", response_model=DocumentOut)
def update_header_meta(doc_id: str, payload: HeaderMeta, db: Session = Depends(get_db)) -> DocumentOut:
    doc = _get_doc(db, doc_id)
    doc.header_meta = json.dumps(payload.model_dump(), ensure_ascii=False)
    db.commit()
    return _document_out(db, doc)


@router.get("/{doc_id}/items", response_model=ItemsOut)
def get_items(doc_id: str, db: Session = Depends(get_db)) -> ItemsOut:
    doc = _get_doc(db, doc_id)
    items = db.scalars(
        select(CatiItem).where(CatiItem.document_id == doc_id).order_by(CatiItem.order_index)
    ).all()
    return ItemsOut(
        document_id=doc_id,
        method=doc.extraction_method,
        warnings=_extraction_warnings(doc),
        items=[_item_out(i) for i in items],
    )


@router.post("/{doc_id}/extract", response_model=ItemsOut)
def reextract(doc_id: str, refresh: bool = True, db: Session = Depends(get_db)) -> ItemsOut:
    doc = _get_doc(db, doc_id)
    if not doc.storage_path or not Path(doc.storage_path).is_file():
        raise AppError("DOCUMENT_FILE_MISSING", "Fichier PDF source introuvable.", status_code=410)

    mistral = _mistral_or_none(db)
    pdf_map = pdf_map_of(get_profile(db, doc.profile_id))
    res = extract_bom(doc.storage_path, mistral=mistral, llm_enabled=mistral is not None, pdf_map=pdf_map)
    doc.page_count = int(res["page_count"])
    doc.extraction_method = res["method"]
    doc.status = "extracted"
    doc.extraction_meta = dumps_meta(res["warnings"])
    _persist_items(db, doc, res["items"])
    db.flush()
    _run_and_store_challenge(db, doc, mistral)
    db.commit()
    return get_items(doc_id, db)


@router.post("/{doc_id}/challenge", response_model=ChallengeReport)
def challenge(doc_id: str, db: Session = Depends(get_db)) -> ChallengeReport:
    """Relance le controle LLM (relecture independante + diff). Gracieux si LLM OFF."""
    doc = _get_doc(db, doc_id)
    if not doc.storage_path or not Path(doc.storage_path).is_file():
        raise AppError("DOCUMENT_FILE_MISSING", "Fichier PDF source introuvable.", status_code=410)
    _run_and_store_challenge(db, doc, _mistral_or_none(db))
    db.commit()
    return _challenge_report(doc)


@router.get("/{doc_id}/challenge", response_model=ChallengeReport)
def get_challenge(doc_id: str, db: Session = Depends(get_db)) -> ChallengeReport:
    return _challenge_report(_get_doc(db, doc_id))
