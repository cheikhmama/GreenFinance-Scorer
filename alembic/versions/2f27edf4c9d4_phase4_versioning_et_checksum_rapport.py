"""phase4_versioning_et_checksum_rapport

Revision ID: 2f27edf4c9d4
Revises: 6da7bdb795f8
Create Date: 2026-09-02 16:04:46.709345

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2f27edf4c9d4'
down_revision: str | Sequence[str] | None = '6da7bdb795f8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAME = 'fk_rapport_esg_rapport_precedent_id_rapport_esg'


def upgrade() -> None:
    """Upgrade schema."""
    # server_default requis : la table a déjà des lignes réelles, une colonne NOT NULL sans
    # valeur par défaut échouerait à la création. 1 reflète le sens du champ pour un rapport
    # déjà existant (première et seule version connue).
    op.add_column(
        'rapport_esg',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column('rapport_esg', sa.Column('rapport_precedent_id', sa.Uuid(), nullable=True))
    op.add_column(
        'rapport_esg',
        sa.Column('checksum_sha256', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        op.f('ix_rapport_esg_checksum_sha256'), 'rapport_esg', ['checksum_sha256'], unique=False
    )
    op.create_foreign_key(
        _FK_NAME, 'rapport_esg', 'rapport_esg', ['rapport_precedent_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(_FK_NAME, 'rapport_esg', type_='foreignkey')
    op.drop_index(op.f('ix_rapport_esg_checksum_sha256'), table_name='rapport_esg')
    op.drop_column('rapport_esg', 'checksum_sha256')
    op.drop_column('rapport_esg', 'rapport_precedent_id')
    op.drop_column('rapport_esg', 'version')
