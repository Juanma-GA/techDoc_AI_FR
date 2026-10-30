"""Routes /api/v1/documents/{id}/resources - DMRL, CIR, regles client BREX.

Ressources optionnelles attachees a un document :

    dmrl        -> pilote le decoupage en Data Modules + genere la PMC
    cir         -> contenus partages (warnings, cautions, outillages)
    brex_rules  -> regles redactionnelles du client (JSON)

Toutes sont facultatives : sans elles, l'assistant fonctionne comme avant.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote
from zipfile import BadZipFile

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from lxml import etree
from sqlalchemy.orm import Session

from app.api_models import DmrlEntryOut, ResourceUploadOut
from app.config import settings
from app.core import dm_header as dm_header_mod
from app.core import dmrl as dmrl_mod
from app.core import migration_inputs
from app.core import wizard_resources as wres
from app.core.brex_rules import load_brex_rules
from app.core.cir import load_cir
from app.core.demo_mode import is_demo_mode
from app.core.errors import AppError
from app.core.fs import publish_file, remove_files
from app.core.pmc import pmc_filename
from app.core.uploads import UPLOAD_LOCK, staged_upload
from app.db.models import Document
from app.db.session import get_db

router = APIRouter(prefix="/documents", tags=["resources"])

_KINDS = {
    "dmrl": {".xlsx", ".xlsm", ".csv", ".json"},
    "cir": {".xml"},
    "brex_rules": {".json"},
    "dm_header": {".json", ".xml"},
}


def _require(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
    return doc


def _store(doc: Document, kind: str, suffix: str, raw: Path) -> Path:
    directory = Path(doc.storage_path).parent
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"document_{doc.id}_{kind}{suffix}"
    publish_file(raw, path)
    return path


@router.post("/{doc_id}/resources/{kind}", response_model=ResourceUploadOut)
def upload_resource(
    doc_id: str, kind: str, response: Response,
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> dict:
    if kind not in _KINDS:
        raise AppError("BAD_RESOURCE", f"Ressource inconnue : {kind}", 422)
    doc = _require(db, doc_id)
    if kind == "brex_rules" and is_demo_mode(db):
        raise AppError("DEMO_BREX_DISABLED", "Les règles BREX ne sont pas disponibles en mode démo.", 409)
    original_filename = file.filename or "resource"
    suffix = Path(original_filename).suffix.lower()
    if suffix not in _KINDS[kind]:
        raise AppError(
            "BAD_RESOURCE_FORMAT",
            f"Extension attendue pour {kind} : {', '.join(sorted(_KINDS[kind]))}",
            422,
        )
    with staged_upload(
        file.file, Path(doc.storage_path).parent, settings.max_upload_size_bytes, suffix=suffix,
    ) as (staging, digest):
        with UPLOAD_LOCK:
            db.refresh(doc, attribute_names=[
                "resource_sha256_json", "dmrl_path", "cir_path", "brex_rules_path", "dm_header_path",
            ])
            hashes = json.loads(doc.resource_sha256_json or "{}")
            previous = hashes.get(kind)
            saved_path = getattr(doc, f"{kind}_path")
            if (previous and previous["sha256"] == digest and saved_path
                    and Path(saved_path).suffix.lower() == suffix and Path(saved_path).is_file()):
                migration_inputs.save_document(db, doc, resource_filename=(kind, original_filename))
                db.commit()
                response.headers["X-Reused"] = "true"
                return {"kind": kind, "count": previous["count"]}
            try:
                result = _parse_resource(doc, kind, staging)
            except (ValueError, KeyError, BadZipFile, etree.XMLSyntaxError) as exc:
                raise AppError(
                    "BAD_RESOURCE_CONTENT", "Le contenu de la ressource est invalide.", 422,
                    detail={"error_type": type(exc).__name__},
                ) from exc
            path = _store(doc, kind, suffix, staging)
            setattr(doc, f"{kind}_path", str(path))
            hashes[kind] = {"sha256": digest, "count": result["count"]}
            doc.resource_sha256_json = json.dumps(hashes)
            migration_inputs.save_document(db, doc, resource_filename=(kind, original_filename))
            db.commit()
            return result


def _parse_resource(doc: Document, kind: str, path: Path) -> dict:
    if kind == "dmrl":
        entries = dmrl_mod.load_dmrl(path, issue=doc.s1000d_issue)
        wres.save_dmrl(doc, entries)
        result = {"kind": kind, "count": len(entries)}
    elif kind == "cir":
        entries_cir = load_cir(path)
        result = {"kind": kind, "count": len(entries_cir)}
    elif kind == "brex_rules":
        rules = load_brex_rules(path)
        result = {"kind": kind, "count": len(rules)}
    else:
        template = dm_header_mod.load_header_template(path)
        doc.dm_header_json = json.dumps(template, ensure_ascii=False)
        result = {"kind": kind, "count": 1}
    return result


@router.delete("/{doc_id}/resources/{kind}", response_model=ResourceUploadOut)
def remove_resource(doc_id: str, kind: str, db: Session = Depends(get_db)) -> dict:
    if kind not in _KINDS:
        raise AppError("BAD_RESOURCE", f"Ressource inconnue : {kind}", 422)
    with UPLOAD_LOCK:
        doc = _require(db, doc_id)
        previous = getattr(doc, f"{kind}_path")
        setattr(doc, f"{kind}_path", None)
        if kind == "dmrl":
            doc.dmrl_json = None
        if kind == "dm_header":
            doc.dm_header_json = None
        hashes = json.loads(doc.resource_sha256_json or "{}")
        hashes.pop(kind, None)
        doc.resource_sha256_json = json.dumps(hashes)
        migration_inputs.remove_resource(db, doc, kind)
        db.commit()
        if previous:
            remove_files([Path(previous)])
    return {"kind": kind, "count": 0}


@router.get("/{doc_id}/dmrl", response_model=list[DmrlEntryOut], response_model_exclude_unset=True)
def get_dmrl(doc_id: str, db: Session = Depends(get_db)) -> list[dict]:
    """Entrees de la DMRL attachee (liste vide si aucune)."""
    doc = _require(db, doc_id)
    return [e.to_dict() for e in wres.dmrl_entries(doc)]


@router.get("/{doc_id}/pmc")
def get_pmc(doc_id: str, db: Session = Depends(get_db)) -> Response:
    """PMC XML generee depuis la DMRL du document."""
    doc = _require(db, doc_id)
    xml = wres.pmc_xml(doc)
    if not xml:
        raise AppError("NO_DMRL", "Aucune DMRL attachee : impossible de generer la PMC.", 409)
    download_name = quote(pmc_filename(doc.filename), safe="").replace("'", "%27")
    return Response(
        content=xml, media_type="application/xml",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{download_name}"
        },
    )
