"""champs_etendus_indicateur_esg_donnee_carbone

Revision ID: 9d2b6f8a41ce
Revises: f4a7c3e29b1d
Create Date: 2026-09-24 09:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9d2b6f8a41ce'
down_revision: str | Sequence[str] | None = 'f4a7c3e29b1d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ('indicateur_esg', 'donnee_carbone')


def upgrade() -> None:
    """Upgrade schema."""
    for table in _TABLES:
        op.add_column(table, sa.Column('valeur_brute', sa.String(), nullable=True))
        op.add_column(table, sa.Column('section', sa.String(), nullable=True))
        op.add_column(table, sa.Column('citation_source', sa.String(), nullable=True))
        op.add_column(table, sa.Column('annee_valeur', sa.Integer(), nullable=True))
        op.add_column(
            table,
            sa.Column(
                'confiance',
                sa.Enum(
                    'ELEVE', 'MOYEN', 'FAIBLE', name='niveauconfiance', native_enum=False, length=64,
                ),
                nullable=True,
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in reversed(_TABLES):
        op.drop_column(table, 'confiance')
        op.drop_column(table, 'annee_valeur')
        op.drop_column(table, 'citation_source')
        op.drop_column(table, 'section')
        op.drop_column(table, 'valeur_brute')
