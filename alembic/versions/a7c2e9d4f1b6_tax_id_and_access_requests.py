"""task 5.10: company tax ID, investor / researcher access requests

- `companies.tax_id` (indexed) and `tax_id_type` (`NIF`, `SIREN`, `EIN`, `TAX_ID`): required by
  the public registration, empty for companies created before.
- `access_requests`: an investor's or researcher's self sign-up. The account (`user_id`, CASCADE,
  unique) exists from the request on, without a password; the admin approves (activation link)
  or rejects (reason). `decided_by_id` SET NULL. One detail per role, enforced by a CHECK.

Downgrade: the table and the two columns are dropped; the accounts created by pending or rejected
requests stay, still without a password (they could not log in either way).

Revision ID: a7c2e9d4f1b6
Revises: f5a1c8e3b7d4
Create Date: 2026-10-04 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c2e9d4f1b6'
down_revision: str | Sequence[str] | None = 'f5a1c8e3b7d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TAX_ID_TYPES = ('NIF', 'SIREN', 'EIN', 'TAX_ID')


def _enum(name: str, *valeurs: str) -> sa.Enum:
    return sa.Enum(*valeurs, name=name, native_enum=False, length=64)


def upgrade() -> None:
    op.add_column('companies', sa.Column('tax_id', sa.String(length=32), nullable=True))
    op.add_column(
        'companies', sa.Column('tax_id_type', _enum('taxidtype', *TAX_ID_TYPES), nullable=True)
    )
    op.create_index('ix_companies_tax_id', 'companies', ['tax_id'])

    op.create_table(
        'access_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column(
            'role',
            _enum('role', 'ADMIN', 'ENTERPRISE', 'AUDITOR', 'INVESTOR', 'RESEARCHER', 'INSTITUTION'),
            nullable=False,
        ),
        sa.Column('organization', sa.String(length=200), nullable=False),
        sa.Column(
            'investor_type',
            _enum('investortype', 'INVESTMENT_FUND', 'BANK_INSTITUTIONAL', 'BUSINESS_ANGEL', 'OTHER'),
            nullable=True,
        ),
        sa.Column(
            'research_domain',
            _enum('researchdomain', 'SUSTAINABLE_FINANCE', 'CARBON_FOOTPRINT', 'GOVERNANCE', 'OTHER'),
            nullable=True,
        ),
        sa.Column(
            'status',
            _enum('accessrequeststatus', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'),
            nullable=False,
        ),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('decided_by_id', sa.Uuid(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=2000), nullable=True),
        sa.CheckConstraint("role IN ('INVESTOR', 'RESEARCHER')", name='ck_access_requests_role'),
        sa.CheckConstraint(
            "(role = 'INVESTOR' AND investor_type IS NOT NULL AND research_domain IS NULL)"
            " OR (role = 'RESEARCHER' AND research_domain IS NOT NULL AND investor_type IS NULL)",
            name='ck_access_requests_detail_by_role',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], name='access_requests_user_id_fkey', ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['decided_by_id'],
            ['users.id'],
            name='access_requests_decided_by_id_fkey',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name='access_requests_pkey'),
    )
    op.create_index('ix_access_requests_user_id', 'access_requests', ['user_id'], unique=True)
    op.create_index('ix_access_requests_decided_by_id', 'access_requests', ['decided_by_id'])


def downgrade() -> None:
    op.drop_index('ix_access_requests_decided_by_id', table_name='access_requests')
    op.drop_index('ix_access_requests_user_id', table_name='access_requests')
    op.drop_table('access_requests')
    op.drop_index('ix_companies_tax_id', table_name='companies')
    op.drop_column('companies', 'tax_id_type')
    op.drop_column('companies', 'tax_id')
