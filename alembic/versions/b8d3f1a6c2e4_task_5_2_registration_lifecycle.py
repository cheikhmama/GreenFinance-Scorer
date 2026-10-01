"""task 5.2: company registration lifecycle (follow-up token, mandate letter, kept rejections)

New `companies` columns: `registered_at`, `status_token_hash` (unique), `mandate_letter_path`,
`mandate_letter_uploaded_at`, `info_request_message`, `info_requested_at`,
`info_response_message`, `rejection_reason`, `rejected_at`. `status` gains `INFO_REQUESTED` and
`REJECTED` (VARCHAR, no value CHECK: no schema change for the values themselves).

Downgrade goes back to the pre-5.2 rules: an `INFO_REQUESTED` request returns to
`PENDING_ONBOARDING`, and a `REJECTED` one is deleted together with its never-activated owner
account, as a refusal did before.

Revision ID: b8d3f1a6c2e4
Revises: a4c7e2d9b6f1
Create Date: 2026-10-01 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8d3f1a6c2e4'
down_revision: str | Sequence[str] | None = 'a4c7e2d9b6f1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLONNES = [
    sa.Column('registered_at', sa.DateTime(), nullable=True),
    sa.Column('status_token_hash', sa.String(length=64), nullable=True),
    sa.Column('mandate_letter_path', sa.String(length=255), nullable=True),
    sa.Column('mandate_letter_uploaded_at', sa.DateTime(), nullable=True),
    sa.Column('info_request_message', sa.String(), nullable=True),
    sa.Column('info_requested_at', sa.DateTime(), nullable=True),
    sa.Column('info_response_message', sa.String(), nullable=True),
    sa.Column('rejection_reason', sa.String(), nullable=True),
    sa.Column('rejected_at', sa.DateTime(), nullable=True),
]


def upgrade() -> None:
    """Upgrade schema."""
    for colonne in COLONNES:
        op.add_column('companies', colonne)
    op.create_unique_constraint(
        'companies_status_token_hash_key', 'companies', ['status_token_hash']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE companies SET status = 'PENDING_ONBOARDING' WHERE status = 'INFO_REQUESTED'")
    op.execute(
        """
        WITH refusees AS (
            DELETE FROM companies WHERE status = 'REJECTED' RETURNING owner_user_id
        )
        DELETE FROM users
        WHERE id IN (SELECT owner_user_id FROM refusees) AND password_hash IS NULL
        """
    )
    op.drop_constraint('companies_status_token_hash_key', 'companies', type_='unique')
    for colonne in reversed(COLONNES):
        op.drop_column('companies', colonne.name)
