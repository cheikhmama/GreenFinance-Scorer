"""task 5.8: a draft's file is analysed before submission

A reporting session can now carry its PDF while still a draft: attaching the file runs the
extraction (`EXTRACTING` with no `submitted_at`), the report comes back to `DRAFT` with its
completeness checklist, and only the explicit submission sets `submitted_at` and locks it.

- `ck_esg_reports_file_unless_draft` → `ck_esg_reports_file_and_submission`: a file outside
  `DRAFT` (unchanged), and no `submitted_at` only in `DRAFT` or `EXTRACTING`.
- `uq_esg_reports_one_draft_per_period`: one **unsubmitted** report per company, fiscal year and
  type (`submitted_at IS NULL`, was `status = 'DRAFT'`), so a draft being analysed still counts.

Downgrade: a draft whose file is still being analysed goes back to `DRAFT` (its file is kept, as
the former rule allowed); extracted values stay attached to it.

Revision ID: f5a1c8e3b7d4
Revises: e3b8c5d1f9a2
Create Date: 2026-10-03 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f5a1c8e3b7d4'
down_revision: str | Sequence[str] | None = 'e3b8c5d1f9a2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint('ck_esg_reports_file_unless_draft', 'esg_reports', type_='check')
    op.create_check_constraint(
        'ck_esg_reports_file_and_submission',
        'esg_reports',
        "(status = 'DRAFT' OR source_file IS NOT NULL) "
        "AND (submitted_at IS NOT NULL OR status IN ('DRAFT', 'EXTRACTING'))",
    )
    op.drop_index('uq_esg_reports_one_draft_per_period', table_name='esg_reports')
    op.create_index(
        'uq_esg_reports_one_draft_per_period',
        'esg_reports',
        ['company_id', 'fiscal_year', 'type'],
        unique=True,
        postgresql_where=sa.text('submitted_at IS NULL'),
    )


def downgrade() -> None:
    op.execute("UPDATE esg_reports SET status = 'DRAFT' WHERE submitted_at IS NULL")
    op.drop_index('uq_esg_reports_one_draft_per_period', table_name='esg_reports')
    op.create_index(
        'uq_esg_reports_one_draft_per_period',
        'esg_reports',
        ['company_id', 'fiscal_year', 'type'],
        unique=True,
        postgresql_where=sa.text("status = 'DRAFT'"),
    )
    op.drop_constraint('ck_esg_reports_file_and_submission', 'esg_reports', type_='check')
    op.create_check_constraint(
        'ck_esg_reports_file_unless_draft',
        'esg_reports',
        "status = 'DRAFT' OR (source_file IS NOT NULL AND submitted_at IS NOT NULL)",
    )
