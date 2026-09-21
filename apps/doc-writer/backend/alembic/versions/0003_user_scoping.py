"""Add Document.user_email + Session.user_email (MFA pilot R1, §3).

Backfills pre-existing rows (user_email IS NULL after the column is added) to
`settings.legacy_user_email` -- fails loudly instead of guessing when that
setting is empty AND there are rows to backfill, so pre-existing local data
never becomes silently invisible once per-user filtering is enabled (no data
loss, per the pilot's explicit scope decision).

`Message` deliberately has NO user_email column: it belongs to a Session and
inherits ownership through session_id -- no redundant column to keep in sync.

Also fixes a real cross-user data leak this surfaced: `documents.sha256` had
a GLOBAL unique index. Two different users uploading the same file content
would collide at the DB level, and the app's dedup check (documents.py) would
hand the second user the FIRST user's document_id/chunk_count -- an
ownership leak, not just a UX quirk. Replaced with a composite unique
constraint on (user_email, sha256): dedup now scopes per user (or globally
when user_email is NULL, i.e. auth disabled -- unchanged tier1 behavior).

Revision ID: 0003_user_scoping
Revises: 0002_doc_kind_session_options
Create Date: 2026-09-14 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.config import settings

revision: str = "0003_user_scoping"
down_revision: str | None = "0002_doc_kind_session_options"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _require_legacy_email_if_rows_exist(table: str, conn: sa.Connection) -> None:
    """Pre-flight check, BEFORE any DDL runs. SQLite migrations here run with
    non-transactional DDL (see alembic env.py log), so raising *after*
    `add_column` would leave the column half-added but `alembic_version` not
    bumped -- a retry would then crash on "duplicate column name". Checking
    row counts on the pre-migration schema (no user_email column yet) avoids
    that entirely: a fresh nullable column always starts every existing row
    at NULL, so "table has any rows" is equivalent to "will need backfill"."""
    count = conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
    if count == 0:
        return
    legacy = (settings.legacy_user_email or "").strip().lower()
    if not legacy:
        raise RuntimeError(
            f"Migration 0003_user_scoping: {count} existing row(s) in '{table}' "
            "have no owner and LEGACY_USER_EMAIL is not set. Set it in .env "
            "(the email to which pre-existing local data should be attached) "
            "and re-run `alembic upgrade head` -- refusing to guess, per the "
            "MFA pilot's no-data-loss decision (see "
            "MFA_PILOT_CHECKLIST_DOC-WRITER_2026-09-14.md §3)."
        )


def upgrade() -> None:
    conn = op.get_bind()
    _require_legacy_email_if_rows_exist("documents", conn)
    _require_legacy_email_if_rows_exist("sessions", conn)

    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_email", sa.String(length=320), nullable=True))
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_email", sa.String(length=320), nullable=True))

    legacy = (settings.legacy_user_email or "").strip().lower()
    if legacy:
        conn.execute(sa.text("UPDATE documents SET user_email = :legacy"), {"legacy": legacy})
        conn.execute(sa.text("UPDATE sessions SET user_email = :legacy"), {"legacy": legacy})

    # Index apres backfill (coherent avec Mapped[...] = mapped_column(..., index=True)).
    op.create_index("ix_documents_user_email", "documents", ["user_email"])
    op.create_index("ix_sessions_user_email", "sessions", ["user_email"])

    # sha256 : unicite GLOBALE -> composite (user_email, sha256). Cf. docstring
    # du module : sans ca, deux utilisateurs uploadant le meme fichier
    # entraient en collision et le 2e recevait le document_id du 1er.
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_documents_sha256"))
        batch_op.create_index(batch_op.f("ix_documents_sha256"), ["sha256"], unique=False)
        batch_op.create_unique_constraint(
            "uq_documents_user_email_sha256", ["user_email", "sha256"]
        )


def downgrade() -> None:
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_constraint("uq_documents_user_email_sha256", type_="unique")
        batch_op.drop_index(batch_op.f("ix_documents_sha256"))
        batch_op.create_index(batch_op.f("ix_documents_sha256"), ["sha256"], unique=True)

    op.drop_index("ix_sessions_user_email", table_name="sessions")
    op.drop_index("ix_documents_user_email", table_name="documents")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("user_email")
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_column("user_email")
