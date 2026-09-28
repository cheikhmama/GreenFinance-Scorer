"""rapport_synthese_genere_sur_rapport_esg

Revision ID: 0c09f23a93cb
Revises: 9d2b6f8a41ce
Create Date: 2026-09-24 16:07:37.937668

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0c09f23a93cb'
down_revision: str | Sequence[str] | None = '9d2b6f8a41ce'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'rapport_esg', sa.Column('rapport_synthese_genere', sa.String(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rapport_esg', 'rapport_synthese_genere')
