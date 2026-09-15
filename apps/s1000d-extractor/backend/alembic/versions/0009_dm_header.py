"""client DM header template."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_dm_header"
down_revision: str | None = "0008_pdf_cut_end"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("dm_header_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "dm_header_json")