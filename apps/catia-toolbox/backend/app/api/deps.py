"""Helpers partages entre routes (chargement de noeuds en ParsedNode)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.parser import ParsedNode
from app.db.models import TreeNode


def load_parsed_nodes(db: Session, import_id: uuid.UUID) -> tuple[list[ParsedNode], dict[str, uuid.UUID]]:
    """Reconstruit les ParsedNode (purs) depuis les lignes TreeNode persistees."""
    rows = list(db.scalars(select(TreeNode).where(TreeNode.import_id == import_id)))
    nodes: list[ParsedNode] = []
    id_by_path: dict[str, uuid.UUID] = {}
    for r in rows:
        id_by_path[r.rel_path] = r.id
        parent_path = r.rel_path.rsplit("/", 1)[0] if "/" in r.rel_path else None
        nodes.append(
            ParsedNode(
                rel_path=r.rel_path,
                name=r.name,
                ext=r.ext,
                kind=r.kind,
                depth=r.depth,
                size=r.size,
                mtime=r.mtime,
                parent_path=parent_path,
            )
        )
    return nodes, id_by_path
