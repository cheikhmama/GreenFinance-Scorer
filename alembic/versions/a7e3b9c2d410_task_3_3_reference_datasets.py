"""task 3.3: reference datasets for cross-validation (staging tables)

Jeux de données ESG publics importés par un Chercheur (tâche 3.3, docs/WORKFLOWS.md §3.4) :
reference_datasets (métadonnées : source, licence, échelle, sens des scores) et
reference_dataset_rows (lignes brutes, identifiées par ISIN ou LEI). Tables de préparation,
propres à leur auteur (owner_user_id CASCADE), jamais lues par le calcul des scores de la
plateforme.

Revision ID: a7e3b9c2d410
Revises: c1d4a8e2f935
Create Date: 2026-10-04 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7e3b9c2d410'
down_revision: str | Sequence[str] | None = 'c1d4a8e2f935'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('reference_datasets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('source_url', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
    sa.Column('licence', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('scale_min', sa.Float(), nullable=False),
    sa.Column('scale_max', sa.Float(), nullable=False),
    sa.Column('higher_is_better', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('scale_max > scale_min', name='ck_reference_datasets_scale'),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reference_datasets_owner_user_id'), 'reference_datasets', ['owner_user_id'], unique=False)
    op.create_table('reference_dataset_rows',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.Column('line_number', sa.Integer(), nullable=False),
    sa.Column('isin', sqlmodel.sql.sqltypes.AutoString(length=12), nullable=True),
    sa.Column('lei', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
    sa.Column('company_name', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
    sa.Column('environmental_score', sa.Float(), nullable=True),
    sa.Column('social_score', sa.Float(), nullable=True),
    sa.Column('governance_score', sa.Float(), nullable=True),
    sa.Column('total_score', sa.Float(), nullable=True),
    sa.CheckConstraint('isin IS NOT NULL OR lei IS NOT NULL', name='ck_reference_dataset_rows_identifier'),
    sa.ForeignKeyConstraint(['dataset_id'], ['reference_datasets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reference_dataset_rows_dataset_id'), 'reference_dataset_rows', ['dataset_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema — les jeux de données importés sont perdus."""
    op.drop_index(op.f('ix_reference_dataset_rows_dataset_id'), table_name='reference_dataset_rows')
    op.drop_table('reference_dataset_rows')
    op.drop_index(op.f('ix_reference_datasets_owner_user_id'), table_name='reference_datasets')
    op.drop_table('reference_datasets')
