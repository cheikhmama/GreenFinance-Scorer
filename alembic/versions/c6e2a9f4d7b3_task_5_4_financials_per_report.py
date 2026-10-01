"""task 5.4: PCAF financials move from companies to esg_reports (per fiscal year)

`revenue`, `revenue_currency`, `enterprise_value`, `enterprise_value_currency` and the EVIC date
(`companies.enterprise_value_as_of` → `esg_reports.evic_date`) now belong to the report whose
emissions they accompany.

Upgrade: each company's figures go to its latest VALIDATED report (by `submitted_at`, the order
the PCAF engine uses) or, failing that, to its latest report of any status (by `created_at`), so
that nothing is lost while a report is still in review. A company with figures but no report at
all loses them — there is no fiscal year to attach them to.

Downgrade: each company gets the figures of its latest validated report that has some, or else of
its latest report that has some.

Revision ID: c6e2a9f4d7b3
Revises: b8d3f1a6c2e4
Create Date: 2026-10-01 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c6e2a9f4d7b3'
down_revision: str | Sequence[str] | None = 'b8d3f1a6c2e4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _colonnes(date_evic: str) -> list[sa.Column]:
    return [
        sa.Column('revenue', sa.Numeric(20, 2), nullable=True),
        sa.Column('revenue_currency', sa.String(length=64), nullable=True),
        sa.Column('enterprise_value', sa.Numeric(20, 2), nullable=True),
        sa.Column('enterprise_value_currency', sa.String(length=64), nullable=True),
        sa.Column(date_evic, sa.Date(), nullable=True),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    for colonne in _colonnes('evic_date'):
        op.add_column('esg_reports', colonne)
    op.execute(
        """
        WITH cible AS (
            SELECT DISTINCT ON (r.company_id) r.company_id, r.id AS report_id
            FROM esg_reports r
            ORDER BY r.company_id,
                     (r.status = 'VALIDATED') DESC,
                     CASE WHEN r.status = 'VALIDATED' THEN r.submitted_at END DESC NULLS LAST,
                     r.created_at DESC
        )
        UPDATE esg_reports r
        SET revenue = c.revenue,
            revenue_currency = c.revenue_currency,
            enterprise_value = c.enterprise_value,
            enterprise_value_currency = c.enterprise_value_currency,
            evic_date = c.enterprise_value_as_of
        FROM cible, companies c
        WHERE r.id = cible.report_id
          AND c.id = cible.company_id
          AND (c.revenue IS NOT NULL OR c.enterprise_value IS NOT NULL)
        """
    )
    for nom in ('enterprise_value_as_of', 'enterprise_value_currency', 'enterprise_value',
                'revenue_currency', 'revenue'):
        op.drop_column('companies', nom)


def downgrade() -> None:
    """Downgrade schema."""
    for colonne in _colonnes('enterprise_value_as_of'):
        op.add_column('companies', colonne)
    op.execute(
        """
        WITH source AS (
            SELECT DISTINCT ON (r.company_id) r.*
            FROM esg_reports r
            WHERE r.revenue IS NOT NULL OR r.enterprise_value IS NOT NULL
            ORDER BY r.company_id,
                     (r.status = 'VALIDATED') DESC,
                     CASE WHEN r.status = 'VALIDATED' THEN r.submitted_at END DESC NULLS LAST,
                     r.created_at DESC
        )
        UPDATE companies c
        SET revenue = s.revenue,
            revenue_currency = s.revenue_currency,
            enterprise_value = s.enterprise_value,
            enterprise_value_currency = s.enterprise_value_currency,
            enterprise_value_as_of = s.evic_date
        FROM source s
        WHERE c.id = s.company_id
        """
    )
    for nom in ('evic_date', 'enterprise_value_currency', 'enterprise_value',
                'revenue_currency', 'revenue'):
        op.drop_column('esg_reports', nom)
