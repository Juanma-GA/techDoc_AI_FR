"""Route /api/v1/imports/{id}/tree - arbre imbrique + metriques."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import StructureImport, TreeNode
from app.db.session import get_db
from app.schemas import TreeNodeOut, TreeOut


router = APIRouter(prefix="/imports", tags=["tree"])


def _build_nested(nodes: list[TreeNode]) -> list[TreeNodeOut]:
    """Reconstruit l'arbre imbrique a partir des lignes plates (parent_id)."""
    out_by_id: dict[uuid.UUID, TreeNodeOut] = {}
    for n in nodes:
        out_by_id[n.id] = TreeNodeOut(
            id=n.id,
            rel_path=n.rel_path,
            name=n.name,
            ext=n.ext,
            kind=n.kind,
            depth=n.depth,
            size=n.size,
            mtime=n.mtime,
            children=[],
        )

    roots: list[TreeNodeOut] = []
    for n in nodes:
        node_out = out_by_id[n.id]
        if n.parent_id and n.parent_id in out_by_id:
            out_by_id[n.parent_id].children.append(node_out)
        else:
            roots.append(node_out)

    def _sort(items: list[TreeNodeOut]) -> None:
        items.sort(key=lambda c: (c.kind != "folder", c.name.lower()))
        for c in items:
            _sort(c.children)

    _sort(roots)
    return roots


@router.get("/{import_id}/tree", response_model=TreeOut)
def get_tree(import_id: uuid.UUID, db: Session = Depends(get_db)) -> TreeOut:
    imp = db.get(StructureImport, import_id)
    if imp is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404, detail={"id": str(import_id)})

    nodes = list(
        db.scalars(
            select(TreeNode).where(TreeNode.import_id == import_id).order_by(TreeNode.depth, TreeNode.rel_path)
        )
    )
    return TreeOut(
        import_id=imp.id,
        root_label=imp.root_label,
        node_count=imp.node_count,
        metrics=json.loads(imp.metrics_json or "{}"),
        nodes=_build_nested(nodes),
    )
