"""phase3_revocation_et_audit

Revision ID: 6da7bdb795f8
Revises: b60e8622e4d7
Create Date: 2026-09-02 14:42:37.470155

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6da7bdb795f8'
down_revision: str | Sequence[str] | None = 'b60e8622e4d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('journal_audit',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('acteur_id', sa.Uuid(), nullable=True),
    sa.Column('action', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('type_ressource', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('id_ressource', sa.Uuid(), nullable=True),
    sa.Column('date', sa.DateTime(), nullable=False),
    sa.Column('resultat', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('ancienne_valeur', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('nouvelle_valeur', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('correlation_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('ip', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['acteur_id'], ['utilisateur.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # server_default requis : la table utilisateur a déjà des lignes (comptes existants), une
    # colonne NOT NULL sans valeur par défaut échouerait à la création. false() reflète le sens
    # du champ pour un compte existant (aucun mot de passe temporaire à changer).
    op.add_column(
        'utilisateur',
        sa.Column(
            'doit_changer_mot_de_passe',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('utilisateur', 'doit_changer_mot_de_passe')
    op.drop_table('journal_audit')
