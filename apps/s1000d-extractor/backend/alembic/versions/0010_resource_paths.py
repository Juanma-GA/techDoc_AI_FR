"""Persist the source paths for document resources."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_resource_paths"
down_revision: str | None = "0009_dm_header"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("dmrl_path", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("dm_header_path", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("dm_header_path")
        batch_op.drop_column("dmrl_path")
