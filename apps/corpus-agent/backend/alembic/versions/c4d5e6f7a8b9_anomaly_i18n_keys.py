"""anomaly_i18n_keys

Revision ID: c4d5e6f7a8b9
Revises: b3d4e5f6a7b8
Create Date: 2026-05-20 00:00:00.000000

Ajoute quatre colonnes nullable à `anomalies` pour le rendu i18n côté
front : `message_key` / `message_params_json` (message principal),
`suggestion_key` / `suggestion_params_json` (texte de suggestion).

Quand `message_key` est non-null, le front résout `t(message_key, params)`.
Le champ `message` reste rempli en FR (fallback systématique si la clé
n'existe pas dans le bundle i18n). Pas de migration de données : les
anomalies existantes gardent leur message FR brut.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d5e6f7a8b9'
down_revision: str | None = 'b3d4e5f6a7b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('anomalies', schema=None) as batch_op:
        batch_op.add_column(sa.Column('message_key', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('message_params_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('suggestion_key', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('suggestion_params_json', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('anomalies', schema=None) as batch_op:
        batch_op.drop_column('suggestion_params_json')
        batch_op.drop_column('suggestion_key')
        batch_op.drop_column('message_params_json')
        batch_op.drop_column('message_key')
