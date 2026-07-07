"""Routes /api/v1/documents/{doc_id}/items - edition des lignes extraites."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.documents import _get_doc, _item_out, get_items
from app.core.errors import AppError
from app.db.models import CatiItem
from app.db.session import get_db
from app.schemas import ItemCreate, ItemOut, ItemPatch, ItemsOut, ReorderIn

router = APIRouter(prefix="/documents/{doc_id}/items", tags=["items"])


def _get_item(db: Session, doc_id: str, item_id: str) -> CatiItem:
    item = db.get(CatiItem, item_id)
    if item is None or item.document_id != doc_id:
        raise AppError("ITEM_NOT_FOUND", "Ligne introuvable.", status_code=404)
    return item


@router.patch("/{item_id}", response_model=ItemOut)
def patch_item(doc_id: str, item_id: str, payload: ItemPatch, db: Session = Depends(get_db)) -> ItemOut:
    _get_doc(db, doc_id)
    item = _get_item(db, doc_id, item_id)
    if payload.fields is not None:
        try:
            current = json.loads(item.fields or "{}")
        except (json.JSONDecodeError, TypeError):
            current = {}
        current.update(payload.fields)
        item.fields = json.dumps(current, ensure_ascii=False)
        item.edited = True
    if payload.included is not None:
        item.included = payload.included
    db.commit()
    return _item_out(item)


@router.post("", response_model=ItemOut)
def create_item(doc_id: str, payload: ItemCreate, db: Session = Depends(get_db)) -> ItemOut:
    _get_doc(db, doc_id)
    items = db.scalars(
        select(CatiItem).where(CatiItem.document_id == doc_id).order_by(CatiItem.order_index)
    ).all()

    insert_at = len(items)
    if payload.after_id:
        for idx, it in enumerate(items):
            if it.id == payload.after_id:
                insert_at = idx + 1
                break

    new_item = CatiItem(
        document_id=doc_id,
        order_index=insert_at,
        fields=json.dumps(dict(payload.fields), ensure_ascii=False),
        included=True,
        edited=True,
    )
    db.add(new_item)
    # Decale les suivants.
    for it in items[insert_at:]:
        it.order_index += 1
    db.commit()
    return _item_out(new_item)


@router.delete("/{item_id}", response_model=ItemsOut)
def delete_item(doc_id: str, item_id: str, db: Session = Depends(get_db)) -> ItemsOut:
    _get_doc(db, doc_id)
    item = _get_item(db, doc_id, item_id)
    db.delete(item)
    db.commit()
    return get_items(doc_id, db)


@router.post("/reorder", response_model=ItemsOut)
def reorder_items(doc_id: str, payload: ReorderIn, db: Session = Depends(get_db)) -> ItemsOut:
    _get_doc(db, doc_id)
    by_id = {
        it.id: it
        for it in db.scalars(select(CatiItem).where(CatiItem.document_id == doc_id)).all()
    }
    for idx, iid in enumerate(payload.ordered_ids):
        if iid in by_id:
            by_id[iid].order_index = idx
    db.commit()
    return get_items(doc_id, db)
