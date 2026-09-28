"""statut_couverture_indicateur

Revision ID: f4a7c3e29b1d
Revises: c3e8a1f5d9b2
Create Date: 2026-09-24 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f4a7c3e29b1d'
down_revision: str | Sequence[str] | None = 'c3e8a1f5d9b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'couverture_indicateur',
        sa.Column(
            'statut',
            sa.Enum(
                'TROUVE', 'NON_TROUVE', 'ABSENT_CONFIRME',
                name='statutcouvertureindicateur', native_enum=False, length=64,
            ),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE couverture_indicateur SET statut = CASE WHEN trouve THEN 'TROUVE' ELSE 'NON_TROUVE' END"
    )
    op.alter_column('couverture_indicateur', 'statut', nullable=False)
    op.drop_column('couverture_indicateur', 'trouve')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('couverture_indicateur', sa.Column('trouve', sa.Boolean(), nullable=True))
    op.execute("UPDATE couverture_indicateur SET trouve = (statut = 'TROUVE')")
    op.alter_column('couverture_indicateur', 'trouve', nullable=False)
    op.drop_column('couverture_indicateur', 'statut')
