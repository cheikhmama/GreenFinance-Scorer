"""phase4_annee_reporting_sur_rapport

Revision ID: 67ada0284cf5
Revises: 2f27edf4c9d4
Create Date: 2026-09-02 16:14:40.812081

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '67ada0284cf5'
down_revision: str | Sequence[str] | None = '2f27edf4c9d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rapport_esg', sa.Column('annee_reporting', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rapport_esg', 'annee_reporting')
