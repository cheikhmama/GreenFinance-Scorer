"""resilience_extraction_sur_rapport_esg

Revision ID: a1c9e7d2b4f6
Revises: 028f2ec9199a
Create Date: 2026-09-23 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c9e7d2b4f6'
down_revision: str | Sequence[str] | None = '028f2ec9199a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rapport_esg', sa.Column('extraction_demarree_le', sa.DateTime(), nullable=True))
    op.add_column(
        'rapport_esg',
        sa.Column('tentatives_extraction', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rapport_esg', 'tentatives_extraction')
    op.drop_column('rapport_esg', 'extraction_demarree_le')
