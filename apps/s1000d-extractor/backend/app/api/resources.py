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

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import settings
from app.core import dmrl as dmrl_mod
from app.core import dm_header as dm_header_mod
from app.core import wizard_resources as wres
from app.core.brex_rules import load_brex_rules
from app.core.cir import load_cir
from app.core.errors import AppError
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


def _store(doc_id: str, kind: str, suffix: str, raw: bytes) -> Path:
    directory = Path(settings.storage_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"document_{doc_id}_{kind}{suffix}"
    path.write_bytes(raw)
    return path


@router.post("/{doc_id}/resources/{kind}")
async def upload_resource(
    doc_id: str, kind: str, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> dict:
    if kind not in _KINDS:
        raise AppError("BAD_RESOURCE", f"Ressource inconnue : {kind}", 422)
    doc = _require(db, doc_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _KINDS[kind]:
        raise AppError(
            "BAD_RESOURCE_FORMAT",
            f"Extension attendue pour {kind} : {', '.join(sorted(_KINDS[kind]))}",
            422,
        )
    raw = await file.read()
    if len(raw) > settings.max_upload_size_bytes:
        raise AppError("FILE_TOO_LARGE", "Fichier trop volumineux.", 413)
    path = _store(doc.id, kind, suffix, raw)

    if kind == "dmrl":
        entries = dmrl_mod.load_dmrl(path)      # valide le contenu (leve si invalide)
        wres.save_dmrl(doc, entries)
        result = {"kind": kind, "count": len(entries)}
    elif kind == "cir":
        entries_cir = load_cir(path)
        doc.cir_path = str(path)
        result = {"kind": kind, "count": len(entries_cir)}
    elif kind == "brex_rules":
        rules = load_brex_rules(path)
        doc.brex_rules_path = str(path)
        result = {"kind": kind, "count": len(rules)}
    else:
        template = dm_header_mod.load_header_template(path)
        doc.dm_header_json = json.dumps(template, ensure_ascii=False)
        result = {"kind": kind, "count": 1}
    db.commit()
    return result


@router.get("/{doc_id}/dmrl")
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
    return Response(
        content=xml, media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{doc.id}_pmc.xml"'},
    )
