"""Backfill `suggestions.source_kind` pour les lignes existantes.

La migration 0013 a ajoute la colonne avec `server_default="norme"` : toute
suggestion generee AVANT ce lot logiciel s'est donc retrouvee etiquetee
"norme" meme si elle venait en realite d'une regle custom, d'unites, de mise
en page ou d'un scan checklist (AI_SCAN) — le filtre "Source" de la liste des
anomalies ne trouvait alors rien pour ces cas sur les analyses deja faites.

Recalcule `source_kind` a partir de `rule_kind`/`rule_code` avec la meme
logique que `rules_engine.classify_source`, en SQL pur (portable SQLite/
Postgres, pas de dependance a l'ORM).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014_backfill_source_kind"
down_revision: str | None = "0013_source_kind_and_doc_mapping"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql(
        """
        UPDATE suggestions
        SET source_kind = CASE
            WHEN rule_kind IN ('units', 'layout', 'vision') THEN 'transverse'
            WHEN rule_kind = 'custom' AND rule_code = 'AI_SCAN' THEN 'checklist'
            WHEN rule_kind = 'custom' THEN 'regle'
            WHEN rule_kind = 'standard' AND rule_code = 'DOCX_REVISION_BAR' THEN 'transverse'
            WHEN rule_kind = 'standard' THEN 'norme'
            ELSE 'transverse'
        END
        """
    )


def downgrade() -> None:
    # Pas d'annulation ciblee : la colonne reste (retour a la valeur par
    # defaut serait une perte d'information, pas un vrai rollback utile).
    pass
