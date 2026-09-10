"""Routes /api/v1/documents/{id}/wizard - configuration etape par etape.

Flux : start -> (split) -> advance -> (type) -> advance -> (structure) ->
advance -> (generate). `update` recalcule l'etape courante sans avancer
(ex. changer le niveau de decoupage et re-previsualiser).
"""

from __future__ import annotations

import asyncio
import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, Body, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core import wizard
from app.core.errors import AppError
from app.db.models import Document
from app.db.session import SessionLocal, get_db

router = APIRouter(prefix="/documents", tags=["wizard"])


def _require(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
    return doc


def _image_paths(doc_id: str) -> list[Path]:
    directory = wizard.images_dir(doc_id)
    if not directory.exists():
        return []
    return sorted(
        (
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ),
        key=lambda path: path.name.lower(),
    )


@router.post("/{doc_id}/wizard/start")
def wizard_start(doc_id: str, db: Session = Depends(get_db)) -> dict:
    return wizard.start(db, _require(db, doc_id))


@router.post("/{doc_id}/wizard/start_stream")
async def wizard_start_stream(doc_id: str, db: Session = Depends(get_db)) -> EventSourceResponse:
    """Demarre l'assistant en streamant la progression (parse / ocr / infer /
    split / classify) ; l'evenement `done` porte l'etat initial (etape split)."""
    doc = _require(db, doc_id)
    doc_id = doc.id

    async def gen():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def cb(step: str, pct: int) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("progress", {"step": step, "pct": pct}))

        def work() -> dict:
            s = SessionLocal()
            try:
                d = s.get(Document, doc_id)
                if d is None:
                    raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
                return wizard.start(s, d, progress_cb=cb)
            finally:
                s.close()

        task = asyncio.create_task(asyncio.to_thread(work))
        yield {"event": "session", "data": json.dumps({"document_id": doc_id})}
        while True:
            getter = asyncio.ensure_future(queue.get())
            done, _ = await asyncio.wait({getter, task}, return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                event, data = getter.result()
                yield {"event": event, "data": json.dumps(data)}
            else:
                getter.cancel()
            if task.done() and queue.empty():
                break
        try:
            yield {"event": "done", "data": json.dumps(task.result())}
        except Exception as exc:
            code = exc.code if isinstance(exc, AppError) else "START_FAILED"
            yield {"event": "error", "data": json.dumps({"code": code, "message": str(exc)})}

    return EventSourceResponse(gen())


@router.get("/{doc_id}/wizard")
def wizard_state(doc_id: str, db: Session = Depends(get_db)) -> dict:
    doc = _require(db, doc_id)
    if not doc.wizard_step:
        raise AppError("WIZARD_NOT_STARTED", "Lance d'abord /wizard/start.", 409)
    return wizard.state(doc)


@router.post("/{doc_id}/wizard/update")
def wizard_update(doc_id: str, params: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
    return wizard.update(db, _require(db, doc_id), params)


@router.post("/{doc_id}/wizard/advance")
def wizard_advance(doc_id: str, params: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
    return wizard.advance(db, _require(db, doc_id), params)


@router.post("/{doc_id}/wizard/back")
def wizard_back(doc_id: str, db: Session = Depends(get_db)) -> dict:
    return wizard.back(db, _require(db, doc_id))


@router.get("/{doc_id}/wizard/dm/{dm_id}/xml")
def wizard_dm_xml(doc_id: str, dm_id: str, db: Session = Depends(get_db)) -> Response:
    doc = _require(db, doc_id)
    xml = wizard.dm_xml(doc, dm_id)
    return Response(
        content=xml, media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{doc.id}_{dm_id}.xml"'},
    )


@router.get("/{doc_id}/wizard/images")
def wizard_images(doc_id: str, db: Session = Depends(get_db)) -> list[str]:
    """Liste les illustrations extraites du document."""
    _require(db, doc_id)
    return [path.name for path in _image_paths(doc_id)]


@router.get("/{doc_id}/wizard/images/{name}")
def wizard_image(doc_id: str, name: str, db: Session = Depends(get_db)) -> Response:
    _require(db, doc_id)
    # Empeche toute traversee de repertoire : on ne sert que le basename.
    safe = Path(name).name
    path = wizard.images_dir(doc_id) / safe
    if safe != name or not path.exists() or path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise AppError("IMAGE_NOT_FOUND", "Illustration inconnue.", 404)
    media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return Response(content=path.read_bytes(), media_type=media_type)


@router.get("/{doc_id}/wizard/zip")
def wizard_zip(doc_id: str, db: Session = Depends(get_db)) -> Response:
    import json as _json

    doc = _require(db, doc_id)
    dms = _json.loads(doc.dms_json) if doc.dms_json else []
    ready = [d for d in dms if d.get("xml")]
    if not ready:
        raise AppError("NO_XML", "Aucun XML genere : termine l'etape Generation.", 409)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in ready:
            zf.writestr(f"{d['dm_id']}.xml", d["xml"])
        for img in _image_paths(doc_id):
            zf.write(img, f"illustrations/{img.name}")
    return Response(
        content=buf.getvalue(), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{doc.id}_dms.zip"'},
    )
