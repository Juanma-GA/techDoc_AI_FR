"""Routes /api/v1/documents - upload, extraction (SSE), XML, override.

Pipeline lance en thread (`asyncio.to_thread`) ; la progression remonte via une
queue vers le flux SSE. Evenements : session -> progress* -> done | error.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.core import dm_header as dm_header_mod
from app.core import ir as ir_mod
from app.core import migration_inputs, pipeline
from app.core import wizard_resources as wres
from app.core.brex import parse_brex
from app.core.brex_generation import serialize_with_brex_guidance
from app.core.brex_profile import extract_brex_dm_code
from app.core.demo_mode import is_demo_mode
from app.core.errors import AppError
from app.core.s1000d_schema import SELECTABLE_ISSUES
from app.core.s1000d_serializer import SerializationDiagnostics, missing_data_fields
from app.core.validator import validate_document, xsd_is_valid
from app.db.models import BrexProfile, DmDocumentLink, DmVersion, Document
from app.db.session import get_db, open_session, storage_directory
from app.parsers import detect_format
from app.parsers.pdf_parser import pdf_page_count
from app.schemas import DocumentOut, ExtractDoneOut, NodeOverrideIn

router = APIRouter(prefix="/documents", tags=["documents"])

_HINTS = {"mixed", "descriptive", "procedural"}


def _require_single_document_workflow(doc: Document) -> None:
    if doc.wizard_step:
        raise AppError(
            "WIZARD_WORKFLOW_REQUIRED",
            "Ce document utilise le wizard : modifiez et exportez ses DMs dans ce parcours.",
            409,
        )


def _storage(db: Session) -> Path:
    p = storage_directory(db)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _to_out(d: Document) -> DocumentOut:
    vcount = len(json.loads(d.violations_json)) if d.violations_json else 0
    return DocumentOut(
        id=d.id, filename=d.filename, source_format=d.source_format,
        s1000d_issue=d.s1000d_issue, context_hint=d.context_hint, status=d.status,
        dm_type=d.dm_type, page_count=d.page_count, has_xml=bool(d.xml_path),
        violation_count=vcount, created_at=d.created_at.isoformat(),
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentOut]:
    rows = db.scalars(select(Document).order_by(Document.created_at.desc())).all()
    return [_to_out(d) for d in rows]


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, db: Session = Depends(get_db)) -> DocumentOut:
    return _to_out(_require(db, doc_id))


@router.delete("/{doc_id}")
def delete_document(
    doc_id: str,
    confirm_token: str = Query("", min_length=10),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete one document and its generated files after explicit confirmation."""
    if not confirm_token:
        raise AppError(
            "DELETE_NOT_CONFIRMED",
            "Suppression non confirmée. Utilisez le double-clic de confirmation.",
            422,
        )
    doc = _require(db, doc_id)
    import shutil

    from app.core.wizard import images_dir

    for path in (
        doc.storage_path, doc.pdf_cut_path, doc.xml_path, doc.dmrl_path,
        doc.dm_header_path, doc.cir_path, doc.brex_rules_path,
    ):
        if path:
            Path(path).unlink(missing_ok=True)
    shutil.rmtree(images_dir(doc.id, root=Path(doc.storage_path).parent), ignore_errors=True)
    db.query(DmDocumentLink).filter(DmDocumentLink.doc_id == doc.id).delete()
    db.query(DmVersion).filter(DmVersion.doc_id == doc.id).delete()
    db.delete(doc)
    db.commit()
    return {"id": doc_id, "status": "deleted"}


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    s1000d_issue: str = Form("4.2"),
    context_hint: str = Form("mixed"),
    brex_id: str | None = Form(None),
    db: Session = Depends(get_db),
) -> DocumentOut:
    if s1000d_issue not in SELECTABLE_ISSUES:
        raise AppError("BAD_ISSUE", f"Issue non supportee : {s1000d_issue}", 422)
    if context_hint not in _HINTS:
        raise AppError("BAD_HINT", f"Hint invalide : {context_hint}", 422)
    if brex_id and is_demo_mode(db):
        raise AppError("DEMO_BREX_DISABLED", "Les profils BREX ne sont pas disponibles en mode démo.", 409)
    fmt = detect_format(file.filename or "")
    raw = await file.read()
    if len(raw) > settings.max_upload_size_bytes:
        raise AppError("FILE_TOO_LARGE", "Document trop volumineux.", 413)
    if brex_id:
        profile = db.get(BrexProfile, brex_id)
        if profile is None:
            raise AppError("BREX_NOT_FOUND", "Profil BREX inconnu.", 404)
        if profile.s1000d_issue != s1000d_issue:
            raise AppError(
                "BREX_ISSUE_MISMATCH",
                f"Issue BREX {profile.s1000d_issue} differente de l'Issue DM {s1000d_issue}.",
                422,
            )

    doc = Document(
        filename=file.filename or f"document.{fmt}", source_format=fmt,
        s1000d_issue=s1000d_issue, context_hint=context_hint, brex_id=brex_id,
        storage_path="", status="uploaded",
    )
    db.add(doc)
    db.flush()
    path = _storage(db) / f"document_{doc.id}.{fmt}"
    path.write_bytes(raw)
    doc.storage_path = str(path)
    if fmt == "pdf":
        try:
            doc.page_count = pdf_page_count(path)
        except Exception:
            doc.page_count = None
    migration_inputs.save_document(db, doc, filename=file.filename or doc.filename)
    db.commit()
    return _to_out(doc)


@router.post("/{doc_id}/extract")
async def extract(doc_id: str, db: Session = Depends(get_db)) -> EventSourceResponse:
    doc = _require(db, doc_id)
    _require_single_document_workflow(doc)
    demo_mode = is_demo_mode(db)
    doc_id = doc.id  # detache de la session avant le thread

    async def event_gen():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def cb(step: str, pct: int) -> None:
            loop.call_soon_threadsafe(
                queue.put_nowait, ("progress", {"step": step, "pct": pct})
            )

        def work() -> dict:
            return _run_and_persist(doc_id, cb, demo_mode)

        task = asyncio.create_task(asyncio.to_thread(work))
        yield {"event": "session", "data": json.dumps({"document_id": doc_id})}
        while True:
            getter = asyncio.ensure_future(queue.get())
            done, _ = await asyncio.wait(
                {getter, task}, return_when=asyncio.FIRST_COMPLETED
            )
            if getter in done:
                event, data = getter.result()
                yield {"event": event, "data": json.dumps(data)}
            else:
                getter.cancel()
            if task.done() and queue.empty():
                break
        try:
            result = task.result()
            yield {"event": "done", "data": json.dumps(result)}
        except Exception as exc:
            code = exc.code if isinstance(exc, AppError) else "EXTRACT_FAILED"
            yield {"event": "error", "data": json.dumps({"code": code, "message": str(exc)})}

    return EventSourceResponse(event_gen())


@router.get("/{doc_id}/result", response_model=ExtractDoneOut)
def get_result(doc_id: str, db: Session = Depends(get_db)) -> ExtractDoneOut:
    """Renvoie le resultat stocke (arbre + violations) d'un document deja
    extrait, sans relancer le pipeline."""
    doc = _require(db, doc_id)
    if not doc.ir_json:
        raise AppError("NO_RESULT", "Aucun resultat : lance l'extraction d'abord.", 409)
    return ExtractDoneOut(
        document_id=doc.id,
        dm_type=doc.dm_type or "descriptive",
        tree=json.loads(doc.ir_json),
        violations=json.loads(doc.violations_json) if doc.violations_json else [],
    )


@router.get("/{doc_id}/xml")
def get_xml(doc_id: str, db: Session = Depends(get_db)) -> Response:
    doc = _require(db, doc_id)
    _require_single_document_workflow(doc)
    if not doc.xml_path or not Path(doc.xml_path).exists():
        raise AppError("NO_XML", "Aucun XML : lance l'extraction d'abord.", 409)
    xml = Path(doc.xml_path).read_text(encoding="utf-8")
    brex_xml = _brex_xml(db, doc.brex_id, doc.s1000d_issue)
    brex_rules = parse_brex(brex_xml) if brex_xml else []
    brex_dm_code = extract_brex_dm_code(brex_xml) if brex_xml else None
    serialization = SerializationDiagnostics()
    if doc.ir_json:
        root = ir_mod.from_dict(json.loads(doc.ir_json))
        resources = wres.load_resources(doc)
        entries = wres.dmrl_data_module_entries(doc)
        metadata = entries[0].to_dict() if entries else None
        xml, serialization, _brex_guided_candidates = serialize_with_brex_guidance(
            root,
            brex_rules,
            issue=doc.s1000d_issue,
            dm_type=doc.dm_type or "descriptive",
            dm_metadata=metadata,
            header_template=dm_header_mod.with_brex_dm_code(
                resources.header_template, brex_dm_code
            ),
        )
        doc.ir_json = json.dumps(ir_mod.to_dict(root), ensure_ascii=False)
        Path(doc.xml_path).write_text(xml, encoding="utf-8")
    violations = validate_document(
        xml,
        issue=doc.s1000d_issue,
        dm_type=doc.dm_type or "descriptive",
        brex_xml=brex_xml,
    )
    violations.extend(serialization.xsd_violations)
    doc.violations_json = json.dumps(violations, ensure_ascii=False)
    missing_fields = missing_data_fields(xml)
    doc.status = (
        "incomplete"
        if (
            not xsd_is_valid(violations)
            or missing_fields
            or any(v.get("severity") == "error" for v in violations)
        )
        else "extracted"
    )
    db.commit()
    return Response(
        content=xml, media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{doc.id}.xml"',
            "X-S1000D-XSD-Valid": str(xsd_is_valid(violations)).lower(),
            "X-S1000D-Missing-Fields": str(len(missing_fields)),
        },
    )


@router.patch("/{doc_id}/nodes/{node_id}", response_model=ExtractDoneOut)
def override_node(
    doc_id: str, node_id: str, body: NodeOverrideIn, db: Session = Depends(get_db)
) -> ExtractDoneOut:
    """Force l'element S1000D d'un noeud (revue humaine), re-serialise, re-valide."""
    doc = _require(db, doc_id)
    _require_single_document_workflow(doc)
    if not doc.ir_json:
        raise AppError("NO_TREE", "Aucun arbre : lance l'extraction d'abord.", 409)
    root = ir_mod.from_dict(json.loads(doc.ir_json))
    node = ir_mod.find_node(root, node_id)
    if node is None:
        raise AppError("NODE_NOT_FOUND", f"Noeud inconnu : {node_id}", 404)
    # Place l'element choisi en tete des candidats (le serialiseur emet [0]).
    chosen = ir_mod.Candidate(body.element, 1.0, "Choix humain")
    node.candidates = [chosen] + [c for c in node.candidates if c.element != body.element]
    node.confidence = 1.0

    brex_xml = _brex_xml(db, doc.brex_id, doc.s1000d_issue)
    brex_rules = parse_brex(brex_xml) if brex_xml else []
    brex_dm_code = extract_brex_dm_code(brex_xml) if brex_xml else None
    resources = wres.load_resources(doc)
    entries = wres.dmrl_data_module_entries(doc)
    metadata = entries[0].to_dict() if entries else None
    xml, serialization, _brex_guided_candidates = serialize_with_brex_guidance(
        root,
        brex_rules,
        issue=doc.s1000d_issue,
        dm_type=doc.dm_type or "descriptive",
        dm_metadata=metadata,
        header_template=dm_header_mod.with_brex_dm_code(
            resources.header_template, brex_dm_code
        ),
    )
    violations = validate_document(
        xml,
        issue=doc.s1000d_issue,
        dm_type=doc.dm_type or "descriptive",
        brex_xml=brex_xml,
    )
    violations.extend(serialization.xsd_violations)
    missing_fields = missing_data_fields(xml)
    doc.status = (
        "incomplete"
        if (
            not xsd_is_valid(violations)
            or missing_fields
            or any(v.get("severity") == "error" for v in violations)
        )
        else "extracted"
    )
    Path(doc.xml_path).write_text(xml, encoding="utf-8")  # type: ignore[arg-type]
    doc.ir_json = json.dumps(ir_mod.to_dict(root), ensure_ascii=False)
    doc.violations_json = json.dumps(violations, ensure_ascii=False)
    db.commit()
    return ExtractDoneOut(
        document_id=doc.id, dm_type=doc.dm_type or "descriptive",
        tree=ir_mod.to_dict(root), violations=violations,  # type: ignore[arg-type]
    )


# --- helpers -----------------------------------------------------------------


def _require(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
    return doc


def _brex_xml(
    db: Session, brex_id: str | None, issue: str | None = None
) -> str | None:
    if not brex_id:
        return None
    b = db.get(BrexProfile, brex_id)
    if b is None:
        raise AppError("BREX_NOT_FOUND", "Profil BREX inconnu.", 404)
    if issue is not None and b.s1000d_issue != issue:
        raise AppError(
            "BREX_ISSUE_MISMATCH",
            f"Issue BREX {b.s1000d_issue} differente de l'Issue DM {issue}.",
            422,
        )
    path = Path(b.xml_path)
    if not path.is_file():
        raise AppError("BREX_FILE_NOT_FOUND", "Le fichier du profil BREX est introuvable.", 404)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AppError("BREX_FILE_UNREADABLE", "Le fichier du profil BREX est illisible.", 500) from exc


def _run_and_persist(doc_id: str, cb, demo_mode: bool = False) -> dict:
    """Execute dans un thread : ouvre sa propre session, lance le pipeline,
    persiste l'arbre + le XML + les violations, renvoie le payload 'done'."""
    db = open_session(demo_mode)
    try:
        doc = db.get(Document, doc_id)
        if doc is None:
            raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
        brex_xml = _brex_xml(db, doc.brex_id, doc.s1000d_issue)
        dmrl_entries = wres.dmrl_data_module_entries(doc)
        try:
            result = pipeline.run(
                doc.storage_path, fmt=doc.source_format, issue=doc.s1000d_issue,
                hint=doc.context_hint, db=db, brex_xml=brex_xml,
                dm_metadata=(dmrl_entries[0].to_dict() if dmrl_entries else None),
                header_template=wres.load_resources(doc).header_template,
                progress_cb=cb,
            )
        except Exception:
            doc.status = "extract_failed"
            db.commit()
            raise
        xml_path = _storage(db) / f"document_{doc.id}.xml"
        xml_path.write_text(result.xml, encoding="utf-8")
        doc.xml_path = str(xml_path)
        doc.dm_type = result.dm_type
        doc.ir_json = json.dumps(result.tree, ensure_ascii=False)
        doc.violations_json = json.dumps(result.violations, ensure_ascii=False)
        missing_fields = missing_data_fields(result.xml)
        doc.status = (
            "incomplete"
            if (
                not xsd_is_valid(result.violations)
                or missing_fields
                or any(v.get("severity") == "error" for v in result.violations)
            )
            else "extracted"
        )
        db.commit()
        return {
            "document_id": doc.id, "dm_type": result.dm_type,
            "tree": result.tree, "violations": result.violations,
        }
    finally:
        db.close()
