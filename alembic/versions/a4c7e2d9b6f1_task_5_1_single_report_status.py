"""task 5.1: report lifecycle as one status (extraction folded back into esg_reports.status)

`extraction_status` disappears; its states become report states:
(SUBMITTED, QUEUED|RUNNING|NOT_STARTED) -> EXTRACTING, (SUBMITTED, FAILED) -> EXTRACTION_FAILED,
(SUBMITTED, DONE) -> AWAITING_ASSIGNMENT, PENDING_AUDIT -> IN_AUDIT. Within EXTRACTING a queued
job is the one with no `extraction_started_at`, so a report still QUEUED loses its start time.

Downgrade rebuilds the pair: a started EXTRACTING report goes back to RUNNING, an unstarted one to
QUEUED; every report past extraction gets DONE, a draft NOT_STARTED.

Revision ID: a4c7e2d9b6f1
Revises: f2a6c9d4e8b1
Create Date: 2026-10-01 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a4c7e2d9b6f1'
down_revision: str | Sequence[str] | None = 'f2a6c9d4e8b1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE esg_reports SET extraction_started_at = NULL "
        "WHERE status = 'SUBMITTED' AND extraction_status IN ('QUEUED', 'NOT_STARTED')"
    )
    op.execute(
        """
        UPDATE esg_reports SET status = CASE
            WHEN status = 'SUBMITTED' AND extraction_status = 'FAILED' THEN 'EXTRACTION_FAILED'
            WHEN status = 'SUBMITTED' AND extraction_status = 'DONE' THEN 'AWAITING_ASSIGNMENT'
            WHEN status = 'SUBMITTED' THEN 'EXTRACTING'
            WHEN status = 'PENDING_AUDIT' THEN 'IN_AUDIT'
            ELSE status
        END
        """
    )
    op.drop_column('esg_reports', 'extraction_status')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('esg_reports', sa.Column('extraction_status', sa.String(length=64), nullable=True))
    op.execute(
        """
        UPDATE esg_reports SET extraction_status = CASE
            WHEN status = 'DRAFT' THEN 'NOT_STARTED'
            WHEN status = 'EXTRACTING' AND extraction_started_at IS NOT NULL THEN 'RUNNING'
            WHEN status = 'EXTRACTING' THEN 'QUEUED'
            WHEN status = 'EXTRACTION_FAILED' THEN 'FAILED'
            ELSE 'DONE'
        END
        """
    )
    op.execute(
        """
        UPDATE esg_reports SET status = CASE
            WHEN status IN ('EXTRACTING', 'EXTRACTION_FAILED', 'AWAITING_ASSIGNMENT') THEN 'SUBMITTED'
            WHEN status = 'IN_AUDIT' THEN 'PENDING_AUDIT'
            ELSE status
        END
        """
    )
    op.alter_column('esg_reports', 'extraction_status', nullable=False)
