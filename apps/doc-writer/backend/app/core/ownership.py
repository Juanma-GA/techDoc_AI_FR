"""Isolation par utilisateur — helpers partages (MFA pilot R1, §3).

Meme regle partout : renvoyer None (-> 404 cote appelant), jamais lever un
403, quand une ressource existe mais appartient a un autre utilisateur — ne
pas reveler l'existence de la ressource d'un tiers. No-op (comportement
tier1 inchange) quand `user` est None (auth desactivee, cf.
app.core.auth.require_authenticated)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser
from app.db.models import Document
from app.db.models import Session as SessionRow


def get_owned_document(
    db: Session, document_id: uuid.UUID, user: AuthenticatedUser | None
) -> Document | None:
    doc = db.get(Document, document_id)
    if doc is None:
        return None
    if user is not None and doc.user_email != user.email:
        return None
    return doc


def get_owned_session(
    db: Session, session_id: uuid.UUID, user: AuthenticatedUser | None
) -> SessionRow | None:
    s = db.get(SessionRow, session_id)
    if s is None:
        return None
    if user is not None and s.user_email != user.email:
        return None
    return s
