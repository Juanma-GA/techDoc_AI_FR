from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.demo_mode import get_demo_enabled
from app.db.models import Document, Suggestion


def documents_in_current_mode(db: Session) -> Select[tuple[Document]]:
    return select(Document).where(Document.is_demo.is_(get_demo_enabled(db)))


def get_document_in_current_mode(
    db: Session,
    document_id: UUID,
) -> Document | None:
    return db.scalar(
        documents_in_current_mode(db).where(Document.id == document_id)
    )


def suggestions_in_current_mode(db: Session) -> Select[tuple[Suggestion]]:
    return (
        select(Suggestion)
        .join(Document, Suggestion.document_id == Document.id)
        .where(Document.is_demo.is_(get_demo_enabled(db)))
    )


def get_suggestion_in_current_mode(
    db: Session,
    suggestion_id: UUID,
) -> Suggestion | None:
    return db.scalar(
        suggestions_in_current_mode(db).where(Suggestion.id == suggestion_id)
    )
