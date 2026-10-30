"""Purge obsolete provider settings while preserving app_config.

Revision ID: 0012_remove_provider_config
Revises: 0011_preliminary_review
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_remove_provider_config"
down_revision: str | None = "0011_preliminary_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM app_config WHERE key IN "
            "('MISTRAL_API_KEY', 'MISTRAL_BASE_URL', 'MISTRAL_CHAT_MODEL', "
            "'MISTRAL_EMBED_MODEL', 'MISTRAL_OCR_MODEL', 'llm_enabled', "
            "'llm_last_test_ok')"
        )
    )


def downgrade() -> None:
    """Purged provider credentials cannot be restored."""
