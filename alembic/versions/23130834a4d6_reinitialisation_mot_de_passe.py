"""reinitialisation_mot_de_passe

Revision ID: 23130834a4d6
Revises: 7589ab0b6fad
Create Date: 2026-09-15 10:25:05.545488

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '23130834a4d6'
down_revision: str | Sequence[str] | None = '7589ab0b6fad'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('reinitialisation_mot_de_passe',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('utilisateur_id', sa.Uuid(), nullable=False),
    sa.Column('jeton_hache', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('date_creation', sa.DateTime(), nullable=False),
    sa.Column('date_expiration', sa.DateTime(), nullable=False),
    sa.Column('utilise_le', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateur.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reinitialisation_mot_de_passe_jeton_hache'), 'reinitialisation_mot_de_passe', ['jeton_hache'], unique=True)
    op.create_index(op.f('ix_reinitialisation_mot_de_passe_utilisateur_id'), 'reinitialisation_mot_de_passe', ['utilisateur_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_reinitialisation_mot_de_passe_utilisateur_id'), table_name='reinitialisation_mot_de_passe')
    op.drop_index(op.f('ix_reinitialisation_mot_de_passe_jeton_hache'), table_name='reinitialisation_mot_de_passe')
    op.drop_table('reinitialisation_mot_de_passe')
