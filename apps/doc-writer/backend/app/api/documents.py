"""Routes /api/v1/documents — upload, list, delete."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.core.indexer import index_document
from app.core.mistral_client import MistralClient, MistralError
from app.core.security import read_and_validate, safe_storage_join
from app.core.versioning import sha256_of_bytes
from app.db.models import Document
from app.db.session import get_db
from app.parsers import SUPPORTED_EXTS, parse_any
from app.schemas import DocumentOut, UploadItemResult, UploadResultOut, ZoneOut, ZonesOut


log = logging.getLogger("doc_writer.documents")

router = APIRouter(prefix="/documents", tags=["documents"])

# Liste blanche stricte : on connaît la liste de formats supportés.
ALLOWED_DOC_EXTS = SUPPORTED_EXTS


VALID_KINDS = {"source", "template", "style"}


@router.get("", response_model=list[DocumentOut])
def list_documents(
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Document]:
    """List documents. Optional `?kind=source|template|style` filter."""
    stmt = select(Document).order_by(Document.uploaded_at.desc())
    if kind:
        if kind not in VALID_KINDS:
            raise AppError(
                "INVALID_KIND",
                f"kind doit etre dans {sorted(VALID_KINDS)}",
                status_code=400,
                detail={"kind": kind},
            )
        stmt = stmt.where(Document.kind == kind)
    return list(db.scalars(stmt))


@router.post("", response_model=UploadResultOut)
def upload_documents(
    files: list[UploadFile] = File(...),
    kind: str = Form(default="source"),
    db: Session = Depends(get_db),
) -> UploadResultOut:
    """Upload N fichiers : valide, dedup sha256, parse, index synchrone.

    Le champ `kind` (form data) indique l'usage :
      - `source` (defaut) : contenu input pour le RAG
      - `template` : structure avec `{{placeholders}}` a remplir
      - `style` : exemple de syntaxe / ton a reproduire

    Si Mistral n'est pas configuré, on enregistre quand même le fichier
    (parsing OK) mais on note `index_error` ; l'indexation n'est faite que
    pour les docs `kind=source` (les templates et styles sont juste lus en
    entier au moment de la generation).
    """
    if kind not in VALID_KINDS:
        raise AppError(
            "INVALID_KIND",
            f"kind doit etre dans {sorted(VALID_KINDS)}",
            status_code=400,
            detail={"kind": kind},
        )
    try:
        mistral = MistralClient.from_db(db)
    except MistralError:
        mistral = None  # type: ignore[assignment]

    results: list[UploadItemResult] = []
    for upload in files:
        try:
            raw, safe_name, ext = read_and_validate(
                upload,
                max_size=settings.max_upload_size_bytes,
                allowed_exts=ALLOWED_DOC_EXTS,
            )
        except AppError as exc:
            results.append(
                UploadItemResult(filename=upload.filename or "?", ok=False, error=exc.message)
            )
            continue

        digest = sha256_of_bytes(raw)

        # Dedup : si le même sha256 existe déjà, on signale skipped.
        existing = db.scalar(select(Document).where(Document.sha256 == digest))
        if existing is not None:
            results.append(
                UploadItemResult(
                    filename=safe_name,
                    ok=True,
                    document_id=existing.id,
                    skipped="duplicate",
                    chunk_count=existing.chunk_count,
                )
            )
            continue

        # Storage : data/storage/doc_<uuid>/<digest>_<safe_name>
        storage_root = safe_storage_join(Path(settings.storage_dir), "documents")
        storage_root.mkdir(parents=True, exist_ok=True)
        new_id = uuid.uuid4()
        doc_dir = safe_storage_join(storage_root, f"doc_{new_id}")
        doc_dir.mkdir(parents=True, exist_ok=True)
        stored = safe_storage_join(doc_dir, f"{digest[:12]}_{safe_name}")
        stored.write_bytes(raw)

        try:
            parsed = parse_any(str(stored))
            extracted_text = parsed.get("text", "")
        except Exception as e:  # noqa: BLE001
            log.exception("parse failed for %s", safe_name)
            results.append(
                UploadItemResult(
                    filename=safe_name, ok=False, error=f"Parse error: {e}"
                )
            )
            try:
                stored.unlink()
            except OSError:
                pass
            continue

        doc = Document(
            id=new_id,
            filename=safe_name,
            mime_type=upload.content_type or "",
            size=len(raw),
            sha256=digest,
            storage_path=str(stored),
            extracted_text=extracted_text,
            kind=kind,
        )
        db.add(doc)
        db.flush()

        chunk_count = 0
        index_err: str | None = None
        # Indexation RAG uniquement pour les docs source. Les templates et
        # styles sont juste lus en entier au moment de la generation.
        if kind == "source":
            if mistral is not None:
                try:
                    chunk_count = index_document(db, doc, mistral)
                except Exception as e:  # noqa: BLE001
                    log.exception("index failed for %s", safe_name)
                    index_err = f"{type(e).__name__}: {e}"
                    doc.index_error = index_err
                    db.commit()
            else:
                doc.index_error = "MISTRAL_NOT_CONFIGURED"
                db.commit()

        results.append(
            UploadItemResult(
                filename=safe_name,
                ok=True,
                document_id=doc.id,
                chunk_count=chunk_count,
                error=index_err,
            )
        )

    db.commit()
    return UploadResultOut(uploaded=results)


_ZONES_CACHE_KIND = "zones_v1"


def _zones_to_dicts(zones: list) -> list[dict]:  # type: ignore[type-arg]
    return [
        {
            "id": z.id,
            "kind": z.kind,
            "slide_index": z.slide_index,
            "slide_title": z.slide_title,
            "label": z.label,
            "location": z.location,
            "target": z.target,
        }
        for z in zones
    ]


def _read_zones_cache(doc: Document) -> tuple[list[dict] | None, bool]:
    """Renvoie (zones_dicts, llm_used) si cache valide, sinon (None, False)."""
    if not doc.extracted_text:
        return None, False
    try:
        data = json.loads(doc.extracted_text)
    except json.JSONDecodeError:
        return None, False
    if not isinstance(data, dict) or data.get("_kind") != _ZONES_CACHE_KIND:
        return None, False
    zones = data.get("zones")
    if not isinstance(zones, list):
        return None, False
    return zones, bool(data.get("llm_used", False))


def _write_zones_cache(doc: Document, zones: list, llm_used: bool, db: Session) -> None:  # type: ignore[type-arg]
    doc.extracted_text = json.dumps(
        {
            "_kind": _ZONES_CACHE_KIND,
            "zones": _zones_to_dicts(zones),
            "llm_used": llm_used,
        },
        ensure_ascii=False,
    )
    db.commit()


def _compute_zones(
    doc: Document,
    db: Session,
) -> tuple[list, bool]:  # type: ignore[type-arg]
    """Calcule les zones (regex deterministes + LLM si Mistral configure).
    Renvoie (zones, llm_used)."""
    from app.core.pptx_template import extract_zones

    try:
        det_zones = extract_zones(doc.storage_path)
    except Exception as e:  # noqa: BLE001
        raise AppError(
            "PARSE_FAILED",
            f"Lecture du template echouee : {type(e).__name__}: {e}",
            status_code=500,
        ) from e

    llm_zones: list = []
    llm_used = False
    try:
        mistral = MistralClient.from_db(db)
    except MistralError:
        mistral = None  # type: ignore[assignment]

    if mistral is not None:
        try:
            from app.core.pptx_llm_analysis import analyse_template

            llm_zones = analyse_template(doc.storage_path, mistral)
            llm_used = True
        except (MistralError, Exception) as e:  # noqa: BLE001
            log.warning("LLM analysis failed for %s: %s", doc.id, e)

    return det_zones + llm_zones, llm_used


@router.get("/{document_id}/zones", response_model=ZonesOut)
def get_zones(
    document_id: uuid.UUID,
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ZonesOut:
    """Liste des zones a remplir detectees dans un template `.pptx`.

    Trois types de zones :
      - `placeholder` : marqueur explicite `{{cle}}` (deterministe)
      - `xxx` : marqueur libre `XXX` (deterministe ; label devine par contexte)
      - `llm` : zone identifiee par Mistral via analyse semantique du template
        (utile pour les cellules de tables vides, boites de texte placeholder
        sans marqueur, layouts complexes)

    Resultat cache dans `Document.extracted_text` apres la 1re analyse.
    `?refresh=true` force une nouvelle passe LLM (bust le cache).

    400 si le document n'est pas un `.pptx` ; 404 si introuvable.
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError(
            "DOCUMENT_NOT_FOUND",
            "Document introuvable.",
            status_code=404,
            detail={"id": str(document_id)},
        )
    if not doc.filename.lower().endswith(".pptx"):
        raise AppError(
            "UNSUPPORTED_TEMPLATE",
            "Seul le format .pptx expose des zones pour l'instant.",
            status_code=400,
            detail={"filename": doc.filename},
        )

    if not refresh:
        cached, llm_used_cached = _read_zones_cache(doc)
        if cached is not None:
            return ZonesOut(
                zones=[ZoneOut(**z) for z in cached],
                llm_used=llm_used_cached,
            )

    zones, llm_used = _compute_zones(doc, db)
    _write_zones_cache(doc, zones, llm_used, db)

    return ZonesOut(
        zones=[
            ZoneOut(
                id=z.id,
                kind=z.kind,
                slide_index=z.slide_index,
                slide_title=z.slide_title,
                label=z.label,
                location=z.location,
                target=z.target,
            )
            for z in zones
        ],
        llm_used=llm_used,
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError(
            "DOCUMENT_NOT_FOUND",
            "Document introuvable.",
            status_code=404,
            detail={"id": str(document_id)},
        )

    # Supprime le fichier sur disque (best-effort).
    try:
        path = Path(doc.storage_path)
        if path.exists():
            path.unlink()
            parent = path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
    except OSError:
        log.warning("could not delete file for %s", doc.id)

    db.delete(doc)
    db.commit()
