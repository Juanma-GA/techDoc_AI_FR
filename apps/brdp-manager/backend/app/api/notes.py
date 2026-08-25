"""Routes /api/v1/notes - note persistante 1-1 attachee a un BRDP."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Note
from app.db.session import get_db
from app.schemas import NoteIn, NoteOut

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/{brdp_id}", response_model=NoteOut)
def read_note(brdp_id: str, db: Session = Depends(get_db)) -> NoteOut:
    row = db.get(Note, brdp_id)
    return NoteOut(text=row.text if row else "")


@router.put("/{brdp_id}", response_model=NoteOut)
def write_note(brdp_id: str, payload: NoteIn, db: Session = Depends(get_db)) -> NoteOut:
    row = db.get(Note, brdp_id)
    if row is None:
        row = Note(brdp_id=brdp_id, text=payload.text)
        db.add(row)
    else:
        row.text = payload.text
    db.commit()
    return NoteOut(text=row.text)
