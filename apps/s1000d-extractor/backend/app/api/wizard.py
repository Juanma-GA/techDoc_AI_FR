"""Routes /api/v1/documents/{id}/wizard - configuration etape par etape.

Flux : start -> (split) -> advance -> (type) -> advance -> (structure) ->
advance -> (generate). `update` recalcule l'etape courante sans avancer
(ex. changer le niveau de decoupage et re-previsualiser).
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from starlette.background import BackgroundTask

from app.core import preliminary_review as preliminary
from app.core import wizard
from app.core import wizard_resources as wres
from app.core.demo_mode import is_demo_mode
from app.core.dm_validation import validate_dm
from app.core.errors import AppError
from app.core.fs import remove_files
from app.core.sse import Progress, stream_threaded_job
from app.core.wizard_fingerprint import dm_xml_fingerprint, xml_context_fingerprint
from app.core.wizard_zip_export import (
    ImageFormat,
    generate_zip_dm_xmls,
    pictogram_image_names,
    prepare_zip_images,
)
from app.db.models import Document
from app.db.session import get_db, open_session
from app.schemas import WizardValidateIn

router = APIRouter(prefix="/documents", tags=["wizard"])


def _dm_filename(dm: dict) -> str:
    """Retourne le nom d'export du DM, avec fallback sur son identifiant technique."""
    candidate = str(dm.get("dmc") or "").strip()
    if candidate and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", candidate):
        return f"{candidate}.xml"
    return f"{dm['dm_id']}.xml"


def _start_options(params: dict) -> tuple[bool, int | None, int | None]:
    cut_pdf = params.get("cut_pdf", True)
    start_page = params.get("start_page")
    end_page = params.get("end_page")
    if not isinstance(cut_pdf, bool):
        raise AppError("PDF_CUT_INVALID", "Le champ cut_pdf doit etre booleen.", 422)
    if start_page is not None and (
        isinstance(start_page, bool) or not isinstance(start_page, int) or start_page < 1
    ):
        raise AppError("PDF_PAGE_INVALID", "Le champ start_page doit etre un entier positif.", 422)
    if end_page is not None and (
        isinstance(end_page, bool) or not isinstance(end_page, int) or end_page < 1
    ):
        raise AppError("PDF_PAGE_INVALID", "Le champ end_page doit etre un entier positif.", 422)
    return cut_pdf, start_page, end_page


def _require(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
    return doc


def _image_paths(doc_id: str, *, root: Path | None = None) -> list[Path]:
    directory = wizard.images_dir(doc_id, root=root)
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
def wizard_start(
    doc_id: str,
    params: dict = Body(default={}),
    db: Session = Depends(get_db),
) -> dict:
    cut_pdf, start_page, end_page = _start_options(params)
    return wizard.start(
        db,
        _require(db, doc_id),
        cut_pdf=cut_pdf,
        start_page=start_page,
        end_page=end_page,
    )


@router.post("/{doc_id}/wizard/start_stream")
async def wizard_start_stream(
    doc_id: str,
    request: Request,
    params: dict = Body(default={}),
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    """Demarre l'assistant en streamant la progression (parse / ocr / infer /
    split / classify) ; l'evenement `done` porte l'etat initial (etape split)."""
    doc = _require(db, doc_id)
    demo_mode = is_demo_mode(db)
    cut_pdf, start_page, end_page = _start_options(params)
    doc_id = doc.id

    def work(progress: Progress) -> dict:
        with open_session(demo_mode) as session:
            document = _require(session, doc_id)
            return wizard.start(
                session, document, progress_cb=progress, cut_pdf=cut_pdf,
                start_page=start_page, end_page=end_page,
            )

    return stream_threaded_job(
        request, work, session_data={"document_id": doc_id}, error_code="START_FAILED",
    )


@router.get("/{doc_id}/wizard")
def wizard_state(doc_id: str, db: Session = Depends(get_db)) -> dict:
    doc = _require(db, doc_id)
    if not doc.wizard_step:
        raise AppError("WIZARD_NOT_STARTED", "Lance d'abord /wizard/start.", 409)
    if doc.wizard_step in {"type", "structure"} and "type" not in wizard.steps_for(doc):
        doc.wizard_step = "split"
        doc.status = "wizard"
        db.commit()
    if doc.wizard_step == "generate" and "preliminary" in wizard.steps_for(doc):
        if any(item["status"] not in {"reviewed", "skipped"} for item in preliminary.view(doc)["reviews"].values()):
            preliminary.prepare(doc)
            doc.wizard_step = "preliminary"
            doc.status = "wizard"
            db.commit()
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
    xml, fingerprint = wizard.read_dm_xml(doc, dm_id, db=db)
    dms = json.loads(doc.dms_json) if doc.dms_json else []
    dm = next((item for item in dms if item.get("dm_id") == dm_id), {"dm_id": dm_id})
    return Response(
        content=xml, media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{_dm_filename(dm)}"',
                 "ETag": f'"{fingerprint}"'},
    )


@router.post("/{doc_id}/wizard/validate")
def wizard_validate(doc_id: str, body: WizardValidateIn, db: Session = Depends(get_db)) -> dict:
    doc = _require(db, doc_id)
    if not doc.wizard_step:
        raise AppError("WIZARD_NOT_STARTED", "Lance d'abord /wizard/start.", 409)
    dms = json.loads(doc.dms_json or "[]")
    by_id = {dm["dm_id"]: dm for dm in dms}
    ids = list(by_id) if body.dm_ids is None else list(dict.fromkeys(body.dm_ids))
    for dm_id in ids:
        if dm_id not in by_id:
            raise AppError("DM_NOT_FOUND", f"DM inconnu : {dm_id}", 404)
    context = xml_context_fingerprint(doc, wizard._brex_xml(db, doc.brex_id, doc.s1000d_issue))
    reference_index = None
    if any(
        by_id[dm_id].get("xml_fingerprint") != dm_xml_fingerprint(by_id[dm_id], context)
        for dm_id in ids
    ):
        dmrl = {entry.dmc: entry.to_dict() for entry in wres.dmrl_entries(doc) if entry.dmc}
        reference_index = wizard.build_reference_index(
            wizard.reference_index_documents(
                dms, dmrl, doc.s1000d_issue,
                root_transform=wizard.reference_root_transform(doc),
            ),
        )
    results = []
    for dm_id in ids:
        xml, _fingerprint = wizard.read_dm_xml(
            doc, dm_id, db=db, fingerprint_context=context, reference_index=reference_index,
        )
        results.append({
            **validate_dm(xml.encode("utf-8"), filename=_dm_filename(by_id[dm_id])),
            "dm_id": dm_id,
        })
    return {"results": results}


@router.get("/{doc_id}/wizard/images")
def wizard_images(doc_id: str, db: Session = Depends(get_db)) -> list[str]:
    """Liste les illustrations extraites du document."""
    doc = _require(db, doc_id)
    return [path.name for path in _image_paths(doc_id, root=Path(doc.storage_path).parent)]


@router.get("/{doc_id}/wizard/images/{name}")
def wizard_image(doc_id: str, name: str, db: Session = Depends(get_db)) -> FileResponse:
    doc = _require(db, doc_id)
    # Empeche toute traversee de repertoire : on ne sert que le basename.
    safe = Path(name).name
    path = wizard.images_dir(doc_id, root=Path(doc.storage_path).parent) / safe
    if safe != name or not path.exists() or path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise AppError("IMAGE_NOT_FOUND", "Illustration inconnue.", 404)
    media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media_type,
                        headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{doc_id}/wizard/zip")
def wizard_zip(
    doc_id: str,
    max_dimension: int | None = Query(default=None, ge=1),
    image_format: ImageFormat = "original",
    db: Session = Depends(get_db),
) -> FileResponse:
    import json as _json

    doc = _require(db, doc_id)
    dms = _json.loads(doc.dms_json) if doc.dms_json else []
    ready = [d for d in dms if d.get("xml")]
    if not ready:
        raise AppError("NO_XML", "Aucun XML genere : termine l'etape Generation.", 409)
    if len(ready) != len(dms):
        raise AppError(
            "DM_INCOMPLETE",
            "Export ZIP impossible : certains DMs n'ont pas pu etre generes.",
            409,
        )
    images, image_name_map = prepare_zip_images(
        _image_paths(doc_id, root=Path(doc.storage_path).parent),
        pictogram_names=pictogram_image_names(doc),
        max_dimension=max_dimension,
        image_format=image_format,
    )
    xml_by_dm = generate_zip_dm_xmls(
        doc,
        [dm["dm_id"] for dm in ready],
        db=db,
        dm_xml_generator=wizard.dm_xml,
        image_name_map=image_name_map,
        root_transform=wizard.reference_root_transform(doc),
    )
    with NamedTemporaryFile(suffix=".zip", dir=Path(doc.storage_path).parent, delete=False) as temporary:
        path = Path(temporary.name)
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for d in ready:
                zf.writestr(_dm_filename(d), xml_by_dm[d["dm_id"]])
            pmc = wres.pmc_xml(doc)
            if pmc:
                zf.writestr(f"PMC/{doc.id}_pmc.xml", pmc)
            for image in images:
                image.write_to(zf)
    except Exception:
        remove_files([path])
        raise
    return FileResponse(
        path, media_type="application/zip", filename=f"{doc.id}_dms.zip",
        background=BackgroundTask(remove_files, [path]),
    )
