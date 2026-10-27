"""Persist procedural review and reader position independently of source trees."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_preliminary_review"
down_revision: str | None = "0010_resource_paths"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("preliminary_review_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "preliminary_review_json")
