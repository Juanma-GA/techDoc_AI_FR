"""Routes /api/v1/documents/{id}/dm-links + dm-versions.

DMRL linking: auto-bind DMRL rows to extracted Data Modules
DM versioning: audit trail + restore capability for Data Modules
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Document, DmDocumentLink, DmVersion
from app.db.session import get_db
from app.schemas import DmDocumentLinkOut, DmVersionContentOut, DmVersionOut, LinkDmrlIn

router = APIRouter(prefix="/documents", tags=["dm-versions"])


def _require(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
    return doc


# ----- DMRL Linking -----


@router.post("/{doc_id}/link-dmrl")
def link_dmrl(
    doc_id: str,
    payload: LinkDmrlIn,
    db: Session = Depends(get_db),
) -> dict:
    """Auto-link DMRL rows to Data Modules or accept manual links.

    mode="auto": parse document.dmrl_json and auto-link by matching dm_code
    mode="manual": use payload.dmrl_links list for manual linking
    """
    doc = _require(db, doc_id)

    if not doc.dmrl_json:
        raise AppError(
            "NO_DMRL",
            "Aucune DMRL attachée au document. Uploadez d'abord une DMRL.",
            400,
        )

    links_to_create = []

    if payload.mode == "auto":
        # Parse dmrl_json and auto-link
        import json

        try:
            dmrl_entries = json.loads(doc.dmrl_json)
        except Exception as e:
            raise AppError("DMRL_PARSE_ERROR", f"Erreur de parsing DMRL: {str(e)}", 400)

        for line_index, entry in enumerate(dmrl_entries, start=1):
            dm_code = entry.get("dmc") or entry.get("dm_code") or entry.get("code")
            if not dm_code:
                continue
            link = DmDocumentLink(
                id=str(uuid4()),
                doc_id=doc_id,
                dmrl_line_id=str(entry.get("line_id") or line_index),
                dm_code=dm_code,
                auto_linked=True,
                created_at=datetime.now(timezone.utc),
            )
            links_to_create.append(link)

    elif payload.mode == "manual":
        # Use provided links
        for link_spec in payload.dmrl_links:
            link = DmDocumentLink(
                id=str(uuid4()),
                doc_id=doc_id,
                dmrl_line_id=link_spec.get("dmrl_line_id"),
                dm_code=link_spec.get("dm_code", ""),
                auto_linked=False,
                created_at=datetime.now(timezone.utc),
            )
            links_to_create.append(link)

    else:
        raise AppError("BAD_MODE", f"Mode inconnu: {payload.mode}", 400)

    # Delete existing links for this document (replace mode)
    db.query(DmDocumentLink).filter(DmDocumentLink.doc_id == doc_id).delete()

    # Add new links
    db.add_all(links_to_create)
    db.commit()

    return {
        "doc_id": doc_id,
        "mode": payload.mode,
        "links_created": len(links_to_create),
    }


@router.get("/{doc_id}/dm-links")
def get_dm_links(doc_id: str, db: Session = Depends(get_db)) -> list[DmDocumentLinkOut]:
    """List DMRL links for a document."""
    doc = _require(db, doc_id)

    links = db.query(DmDocumentLink).filter(DmDocumentLink.doc_id == doc_id).all()

    return [
        DmDocumentLinkOut(
            id=link.id,
            doc_id=link.doc_id,
            dmrl_line_id=link.dmrl_line_id,
            dm_code=link.dm_code,
            auto_linked=link.auto_linked,
            created_at=link.created_at.isoformat() if link.created_at else "",
        )
        for link in links
    ]


# ----- DM Versioning -----


@router.post("/{doc_id}/dm-versions/{dm_code}")
def save_dm_version(
    doc_id: str,
    dm_code: str = Path(..., min_length=1),
    content: str = Query(..., description="DM XML content"),
    author: str = Query("unknown"),
    status: str = Query("draft"),
    notes: str = Query(""),
    db: Session = Depends(get_db),
) -> DmVersionOut:
    """Save a Data Module version (snapshot for audit trail)."""
    doc = _require(db, doc_id)

    version = DmVersion(
        id=str(uuid4()),
        doc_id=doc_id,
        dm_code=dm_code,
        content=content,
        author=author,
        status=status,
        notes=notes or None,
        created_at=datetime.now(timezone.utc),
    )

    db.add(version)
    db.commit()
    db.refresh(version)

    return DmVersionOut(
        id=version.id,
        doc_id=version.doc_id,
        dm_code=version.dm_code,
        author=version.author,
        status=version.status,
        notes=version.notes,
        created_at=version.created_at.isoformat() if version.created_at else "",
        content_length=len(version.content),
    )


@router.get("/{doc_id}/dm-versions")
def get_dm_versions(
    doc_id: str,
    dm_code: str = Query("", description="Filter by dm_code (empty = all)"),
    db: Session = Depends(get_db),
) -> list[DmVersionOut]:
    """List DM versions (snapshots) for a document, optionally filtered by dm_code."""
    doc = _require(db, doc_id)

    query = db.query(DmVersion).filter(DmVersion.doc_id == doc_id)

    if dm_code:
        query = query.filter(DmVersion.dm_code == dm_code)

    versions = query.order_by(DmVersion.created_at.desc()).all()

    return [
        DmVersionOut(
            id=v.id,
            doc_id=v.doc_id,
            dm_code=v.dm_code,
            author=v.author,
            status=v.status,
            notes=v.notes,
            created_at=v.created_at.isoformat() if v.created_at else "",
            content_length=len(v.content),
        )
        for v in versions
    ]


@router.get("/{doc_id}/dm-versions/{version_id}")
def get_dm_version(
    doc_id: str,
    version_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> DmVersionContentOut:
    """Get a specific DM version with full content."""
    doc = _require(db, doc_id)

    version = (
        db.query(DmVersion)
        .filter(DmVersion.doc_id == doc_id, DmVersion.id == version_id)
        .first()
    )

    if version is None:
        raise AppError("VERSION_NOT_FOUND", "Version introuvable.", 404)

    return DmVersionContentOut(
        id=version.id,
        doc_id=version.doc_id,
        dm_code=version.dm_code,
        content=version.content,
        author=version.author,
        status=version.status,
        notes=version.notes,
        created_at=version.created_at.isoformat() if version.created_at else "",
    )


@router.post("/{doc_id}/dm-versions/{version_id}/restore")
def restore_dm_version(
    doc_id: str,
    version_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    """Restore a Data Module to a previous version (creates a new version record).

    This is safe: the old version remains, a new one is created with restored content.
    """
    doc = _require(db, doc_id)

    old_version = (
        db.query(DmVersion)
        .filter(DmVersion.doc_id == doc_id, DmVersion.id == version_id)
        .first()
    )

    if old_version is None:
        raise AppError("VERSION_NOT_FOUND", "Version à restaurer introuvable.", 404)

    # Create a new version record with restored content
    new_version = DmVersion(
        id=str(uuid4()),
        doc_id=doc_id,
        dm_code=old_version.dm_code,
        content=old_version.content,
        author="restore",
        status="restored",
        notes=f"Restored from version {version_id}",
        created_at=datetime.now(timezone.utc),
    )

    db.add(new_version)
    db.commit()
    db.refresh(new_version)

    return {
        "doc_id": doc_id,
        "original_version_id": version_id,
        "restored_version_id": new_version.id,
        "dm_code": new_version.dm_code,
        "created_at": new_version.created_at.isoformat() if new_version.created_at else "",
    }
