"""nom_sur_utilisateur

Revision ID: cc458b3b8aa4
Revises: 67ada0284cf5
Create Date: 2026-09-03 17:01:14.001701

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'cc458b3b8aa4'
down_revision: str | Sequence[str] | None = '67ada0284cf5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable : les comptes existants (créés avant ce champ) n'ont pas de nom rétroactif à
    # inférer -- contrairement à doit_changer_mot_de_passe (6da7bdb795f8), pas de valeur par
    # défaut sensée ici.
    op.add_column('utilisateur', sa.Column('nom', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('utilisateur', 'nom')
