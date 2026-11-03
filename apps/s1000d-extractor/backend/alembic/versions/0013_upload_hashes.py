"""Track upload content hashes without reading existing source files."""

import sqlalchemy as sa

from alembic import op

revision = "0013_upload_hashes"
down_revision = "0012_remove_provider_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("sha256", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("resource_sha256_json", sa.Text(), nullable=True))
    op.create_index("ix_documents_sha256", "documents", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_documents_sha256", table_name="documents")
    op.drop_column("documents", "resource_sha256_json")
    op.drop_column("documents", "sha256")
