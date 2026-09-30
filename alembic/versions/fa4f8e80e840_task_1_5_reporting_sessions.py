"""task 1.5: reporting sessions (DRAFT reports without a file)

Tâche 1.5 : une déclaration peut être ouverte (DRAFT) pour un exercice avant tout dépôt de
fichier, puis soumise (POST /reports/{id}/submit).

1. esg_reports.created_at : création de la ligne, renseignée pour l'existant depuis submitted_at.
2. submitted_at et source_file deviennent nullables — un brouillon n'a encore ni l'un ni l'autre ;
   ck_esg_reports_file_unless_draft impose les deux à tout autre statut.
3. uq_esg_reports_one_draft_per_period : un seul brouillon par entreprise, exercice et type.

Revision ID: fa4f8e80e840
Revises: e7d012541fce
Create Date: 2026-09-30 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fa4f8e80e840'
down_revision: str | Sequence[str] | None = 'e7d012541fce'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('esg_reports', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.execute('UPDATE esg_reports SET created_at = submitted_at')
    op.alter_column('esg_reports', 'created_at', nullable=False)
    op.alter_column('esg_reports', 'submitted_at', existing_type=sa.DateTime(), nullable=True)
    op.alter_column('esg_reports', 'source_file', existing_type=sa.String(), nullable=True)
    op.create_check_constraint(
        'ck_esg_reports_file_unless_draft',
        'esg_reports',
        "status = 'DRAFT' OR (source_file IS NOT NULL AND submitted_at IS NOT NULL)",
    )
    op.create_index(
        'uq_esg_reports_one_draft_per_period',
        'esg_reports',
        ['company_id', 'fiscal_year', 'type'],
        unique=True,
        postgresql_where=sa.text("status = 'DRAFT'"),
    )


def downgrade() -> None:
    """Downgrade schema.

    Les brouillons (sans fichier) ne peuvent pas exister dans l'ancien schéma : ils sont supprimés
    — une déclaration jamais déposée ne porte aucune donnée extraite."""
    op.execute("DELETE FROM esg_reports WHERE status = 'DRAFT'")
    op.drop_index('uq_esg_reports_one_draft_per_period', table_name='esg_reports')
    op.drop_constraint('ck_esg_reports_file_unless_draft', 'esg_reports', type_='check')
    op.alter_column('esg_reports', 'source_file', existing_type=sa.String(), nullable=False)
    op.alter_column('esg_reports', 'submitted_at', existing_type=sa.DateTime(), nullable=False)
    op.drop_column('esg_reports', 'created_at')
