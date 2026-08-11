"""initial empty migration

Revision ID: 440af0be0e05
Revises: 
Create Date: 2026-08-11 10:36:31.784508

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '440af0be0e05'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
