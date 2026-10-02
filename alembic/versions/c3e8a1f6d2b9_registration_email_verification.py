"""task 5.11: registration e-mail verification (6-digit code)

A registration request now waits in `EMAIL_VERIFICATION_PENDING` until its applicant types the
code e-mailed to their professional address; only then does it become `PENDING_ONBOARDING` and
reach the admin. Columns on `companies`: the code's HMAC (never the code itself), when it was
sent and until when it is valid, wrong attempts, and when the address was confirmed.
`status` is a VARCHAR without CHECK (non-native enum): the new value needs no DDL.

Downgrade: the columns are dropped; requests still waiting for their code are deleted with their
owner account (never activated, no password) — they never reached the admin, and the former
schema has no state for them.

Revision ID: c3e8a1f6d2b9
Revises: a7c2e9d4f1b6
Create Date: 2026-10-05 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3e8a1f6d2b9'
down_revision: str | Sequence[str] | None = 'a7c2e9d4f1b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'companies', sa.Column('email_verification_code_hash', sa.String(length=64), nullable=True)
    )
    op.add_column('companies', sa.Column('email_verification_sent_at', sa.DateTime(), nullable=True))
    op.add_column(
        'companies', sa.Column('email_verification_expires_at', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'companies',
        sa.Column(
            'email_verification_attempts', sa.Integer(), nullable=False, server_default='0'
        ),
    )
    op.alter_column('companies', 'email_verification_attempts', server_default=None)
    op.add_column('companies', sa.Column('email_verified_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.execute(
        "DELETE FROM users WHERE id IN (SELECT owner_user_id FROM companies"
        " WHERE status = 'EMAIL_VERIFICATION_PENDING' AND owner_user_id IS NOT NULL)"
    )
    op.execute("DELETE FROM companies WHERE status = 'EMAIL_VERIFICATION_PENDING'")
    op.drop_column('companies', 'email_verified_at')
    op.drop_column('companies', 'email_verification_attempts')
    op.drop_column('companies', 'email_verification_expires_at')
    op.drop_column('companies', 'email_verification_sent_at')
    op.drop_column('companies', 'email_verification_code_hash')
