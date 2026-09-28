"""couverture_indicateur

Revision ID: c3e8a1f5d9b2
Revises: a1c9e7d2b4f6
Create Date: 2026-09-23 00:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3e8a1f5d9b2'
down_revision: str | Sequence[str] | None = 'a1c9e7d2b4f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'couverture_indicateur',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('rapport_id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('trouve', sa.Boolean(), nullable=False),
        sa.Column('pages_examinees', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['rapport_id'], ['rapport_esg.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rapport_id', 'code', name='uq_couverture_indicateur_rapport_code'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('couverture_indicateur')
