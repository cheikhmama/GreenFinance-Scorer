"""task 1.4: company onboarding (who validated the registration, and when)

companies.onboarded_at / onboarded_by_id, posés par la validation d'une inscription publique
(app/admin/onboarding.py). Nuls pour les entreprises existantes : provisionnées directement par
l'Administrateur ou antérieures à la tâche 1.4, elles n'ont jamais eu d'inscription à valider.
onboarded_by_id -> users en SET NULL : supprimer le compte d'un Administrateur ne remet jamais une
entreprise en attente.

Revision ID: e7d012541fce
Revises: 834bf70ae1b9
Create Date: 2026-09-30 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7d012541fce'
down_revision: str | Sequence[str] | None = '834bf70ae1b9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('companies', sa.Column('onboarded_at', sa.DateTime(), nullable=True))
    op.add_column('companies', sa.Column('onboarded_by_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'companies_onboarded_by_id_fkey', 'companies', 'users',
        ['onboarded_by_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_companies_onboarded_by_id', 'companies', ['onboarded_by_id'])


def downgrade() -> None:
    """Downgrade schema — les dates et auteurs de validation sont perdus."""
    op.drop_index('ix_companies_onboarded_by_id', table_name='companies')
    op.drop_constraint('companies_onboarded_by_id_fkey', 'companies', type_='foreignkey')
    op.drop_column('companies', 'onboarded_by_id')
    op.drop_column('companies', 'onboarded_at')
