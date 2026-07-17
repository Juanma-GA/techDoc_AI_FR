"""Routes /api/v1/imports - scan de dossier local OU import de listing CSV/JSON.

ECART STANDARD assume : `POST /imports/scan` lit le systeme de fichiers hors
`data/storage/` (coeur fonctionnel). Lecture metadonnees uniquement, jamais
le contenu ; cap `max_nodes` ; aucune ecriture. Voir README `## Ecarts`.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import nomenclature as nomen
from app.core import onedrive
from app.core.errors import AppError
from app.core import parser as parser_mod
from app.core.parser import ParsedTree
from app.core.security import read_and_validate, safe_under_root
from app.core.tree_metrics import compute_metrics
from app.db.models import StructureImport, TreeNode
from app.db.session import get_db
from app.schemas import (
    ImportOut,
    ScanIn,
    SelectImportIn,
    ZipEntryOut,
    ZipImportIn,
    ZipImportOut,
)


log = logging.getLogger("catia_toolbox.imports")

router = APIRouter(prefix="/imports", tags=["imports"])

_LISTING_EXTS = {".csv", ".json"}


def _persist_tree(db: Session, tree: ParsedTree, *, source_mode: str, source_ref: str) -> StructureImport:
    """Persiste un ParsedTree : import + noeuds + metriques cachees."""
    metrics = compute_metrics(tree.nodes)
    imp = StructureImport(
        source_mode=source_mode,
        root_label=tree.root_label[:500],
        source_ref=source_ref,
        node_count=tree.node_count,
        metrics_json=json.dumps(metrics, ensure_ascii=False),
    )
    db.add(imp)
    db.flush()  # alloue imp.id

    # Les noeuds sont tries par profondeur croissante (cf. parser) : on garantit
    # qu'un parent est insere avant ses enfants pour resoudre parent_id.
    id_by_path: dict[str, uuid.UUID] = {}
    ordered = sorted(tree.nodes, key=lambda n: (n.depth, n.kind != "folder", n.rel_path))
    for n in ordered:
        node_id = uuid.uuid4()
        id_by_path[n.rel_path] = node_id
        db.add(
            TreeNode(
                id=node_id,
                import_id=imp.id,
                parent_id=id_by_path.get(n.parent_path) if n.parent_path else None,
                rel_path=n.rel_path,
                name=n.name[:500],
                ext=n.ext[:40],
                kind=n.kind,
                depth=n.depth,
                size=n.size,
                mtime=n.mtime,
            )
        )
    db.commit()
    db.refresh(imp)
    return imp


def _to_out(imp: StructureImport) -> ImportOut:
    return ImportOut(
        id=imp.id,
        source_mode=imp.source_mode,
        root_label=imp.root_label,
        source_ref=imp.source_ref,
        node_count=imp.node_count,
        created_at=imp.created_at,
        metrics=json.loads(imp.metrics_json or "{}"),
    )


@router.get("", response_model=list[ImportOut])
def list_imports(db: Session = Depends(get_db)) -> list[ImportOut]:
    rows = db.scalars(select(StructureImport).order_by(StructureImport.created_at.desc()))
    return [_to_out(r) for r in rows]


@router.post("/scan", response_model=ImportOut)
def scan_import(payload: ScanIn, db: Session = Depends(get_db)) -> ImportOut:
    tree = parser_mod.scan_folder(payload.path, max_nodes=payload.max_nodes)
    if tree.node_count == 0:
        raise AppError("SCAN_EMPTY", "Aucun fichier trouve dans ce dossier.", status_code=400)
    imp = _persist_tree(db, tree, source_mode="folder", source_ref=payload.path)
    log.info("scan import %s : %d noeuds", imp.id, imp.node_count)
    return _to_out(imp)


@router.post("/select", response_model=ImportOut)
def select_import(payload: SelectImportIn, db: Session = Depends(get_db)) -> ImportOut:
    """Import depuis une selection mixte de fichiers ET dossiers (browser OneDrive).

    Chaque chemin est confine sous la racine du scope (anti path-traversal) avant
    le scan metadonnees-seules.
    """
    if payload.scope not in ("input", "output"):
        raise AppError("SELECT_SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)

    root = onedrive.root_for_scope(db, payload.scope)
    confined: list[str] = [str(safe_under_root(root, p)) for p in payload.paths]

    tree = parser_mod.scan_paths(root, confined, max_nodes=payload.max_nodes)
    if tree.node_count == 0:
        raise AppError("SELECT_EMPTY", "Selection vide ou hors racine.", status_code=400)

    n = len(payload.paths)
    source_ref = confined[0] if n == 1 else f"{n} elements sous {root}"
    imp = _persist_tree(db, tree, source_mode="selection", source_ref=source_ref)
    log.info("select import %s : %d noeuds (%d selectionnes)", imp.id, imp.node_count, n)
    return _to_out(imp)


@router.post("/zip", response_model=ZipImportOut)
def zip_import(payload: ZipImportIn, db: Session = Depends(get_db)) -> ZipImportOut:
    """Import unifie d'un .zip : cree l'import (arbo metadonnees) ET renvoie le
    listing du contenu. Sert a la fois a inspecter un DE (Etape 1) et a fournir
    une source a convertir (Etape 2). Rien n'est extrait ; confine sous la racine.
    """
    if payload.scope not in ("input", "output"):
        raise AppError("SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)
    root = onedrive.root_for_scope(db, payload.scope)
    target = safe_under_root(root, payload.path)
    if not target.is_file():
        raise AppError("ZIP_NOT_FOUND", "Fichier .zip introuvable.", status_code=404, detail={"path": str(target)})
    entries = nomen.list_zip(str(target), max_entries=payload.max_nodes)
    label = target.stem or target.name
    tree = parser_mod.build_tree_from_zip_entries(entries, root_label=label, max_nodes=payload.max_nodes)
    if tree.node_count == 0:
        raise AppError("ZIP_EMPTY", "Archive .zip vide ou illisible.", status_code=400)
    imp = _persist_tree(db, tree, source_mode="zip", source_ref=str(target))
    log.info("zip import %s : %d noeuds", imp.id, imp.node_count)
    out = _to_out(imp)
    return ZipImportOut(
        **out.model_dump(),
        count=len(entries),
        entries=[ZipEntryOut(**e) for e in entries],
    )


@router.post("/upload", response_model=ImportOut)
def upload_import(file: UploadFile = File(...), db: Session = Depends(get_db)) -> ImportOut:
    raw, safe_name, ext = read_and_validate(
        file,
        max_size=settings.max_upload_size_bytes,
        allowed_exts=_LISTING_EXTS,
    )
    tree = parser_mod.parse_listing(raw, ext, root_label=safe_name)
    if tree.node_count == 0:
        raise AppError("LISTING_EMPTY", "Listing sans noeud exploitable.", status_code=400)
    imp = _persist_tree(db, tree, source_mode=ext.lstrip("."), source_ref=safe_name)
    log.info("upload import %s : %d noeuds", imp.id, imp.node_count)
    return _to_out(imp)


@router.get("/{import_id}", response_model=ImportOut)
def get_import(import_id: uuid.UUID, db: Session = Depends(get_db)) -> ImportOut:
    imp = db.get(StructureImport, import_id)
    if imp is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404, detail={"id": str(import_id)})
    return _to_out(imp)


@router.delete("/{import_id}", status_code=204)
def delete_import(import_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    imp = db.get(StructureImport, import_id)
    if imp is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404, detail={"id": str(import_id)})
    db.delete(imp)
    db.commit()
