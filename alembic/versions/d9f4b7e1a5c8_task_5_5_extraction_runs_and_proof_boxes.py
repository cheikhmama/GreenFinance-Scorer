"""task 5.5: extraction provenance (extraction_runs) and proof bounding boxes

New table `extraction_runs` — one row per execution of the extraction pipeline on a report: Docling
version, LLM model, prompt version, start/end, outcome. `esg_metrics` and `carbon_emissions` gain
`extraction_run_id` (SET NULL + index: a run never takes its values with it) and `proof_boxes`
(JSONB, `[]` by default — where the cited value reads on its page).

Rows written before this revision keep no run and no boxes; nothing can be reconstructed for them.

Revision ID: d9f4b7e1a5c8
Revises: c6e2a9f4d7b3
Create Date: 2026-10-01 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd9f4b7e1a5c8'
down_revision: str | Sequence[str] | None = 'c6e2a9f4d7b3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES_EXTRAITES = ('esg_metrics', 'carbon_emissions')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'extraction_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('report_id', sa.Uuid(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=64), nullable=False),
        sa.Column('error', sa.String(length=100), nullable=True),
        sa.Column('docling_version', sa.String(length=50), nullable=False),
        sa.Column('llm_model', sa.String(length=100), nullable=False),
        sa.Column('prompt_version', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ['report_id'], ['esg_reports.id'],
            name='extraction_runs_report_id_fkey', ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name='extraction_runs_pkey'),
    )
    op.create_index('ix_extraction_runs_report_id', 'extraction_runs', ['report_id'])
    for table in TABLES_EXTRAITES:
        op.add_column(table, sa.Column('extraction_run_id', sa.Uuid(), nullable=True))
        op.add_column(
            table,
            sa.Column(
                'proof_boxes',
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        )
        op.create_index(f'ix_{table}_extraction_run_id', table, ['extraction_run_id'])
        op.create_foreign_key(
            f'{table}_extraction_run_id_fkey', table, 'extraction_runs',
            ['extraction_run_id'], ['id'], ondelete='SET NULL',
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES_EXTRAITES:
        op.drop_constraint(f'{table}_extraction_run_id_fkey', table, type_='foreignkey')
        op.drop_index(f'ix_{table}_extraction_run_id', table_name=table)
        op.drop_column(table, 'proof_boxes')
        op.drop_column(table, 'extraction_run_id')
    op.drop_index('ix_extraction_runs_report_id', table_name='extraction_runs')
    op.drop_table('extraction_runs')
