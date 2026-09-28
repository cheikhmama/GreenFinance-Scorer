"""activation_compte_par_email

Revision ID: 028f2ec9199a
Revises: cc31547dadba
Create Date: 2026-09-22 17:16:00.222390

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '028f2ec9199a'
down_revision: str | Sequence[str] | None = 'cc31547dadba'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('activation_compte',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('utilisateur_id', sa.Uuid(), nullable=False),
    sa.Column('jeton_hache', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('date_creation', sa.DateTime(), nullable=False),
    sa.Column('date_expiration', sa.DateTime(), nullable=False),
    sa.Column('utilise_le', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateur.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_activation_compte_jeton_hache'), 'activation_compte', ['jeton_hache'], unique=True)
    op.create_index(op.f('ix_activation_compte_utilisateur_id'), 'activation_compte', ['utilisateur_id'], unique=False)
    op.add_column('utilisateur', sa.Column('date_activation', sa.DateTime(), nullable=True))
    # Rétrocompatibilité : tous les comptes existants ont déjà un mot de passe utilisable
    # (temporaire ou déjà changé) — les considérer activés à leur date de création plutôt que de
    # les verrouiller derrière un lien d'activation qui n'a jamais été émis pour eux. Seuls les
    # comptes créés après cette migration passeront réellement par le flux d'activation.
    op.execute("UPDATE utilisateur SET date_activation = date_creation")
    op.alter_column('utilisateur', 'mot_de_passe_hache',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.drop_column('utilisateur', 'doit_changer_mot_de_passe')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('utilisateur', sa.Column('doit_changer_mot_de_passe', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))
    op.alter_column('utilisateur', 'mot_de_passe_hache',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.drop_column('utilisateur', 'date_activation')
    op.drop_index(op.f('ix_activation_compte_utilisateur_id'), table_name='activation_compte')
    op.drop_index(op.f('ix_activation_compte_jeton_hache'), table_name='activation_compte')
    op.drop_table('activation_compte')
