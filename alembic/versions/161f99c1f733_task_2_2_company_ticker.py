"""task 2.2: company ticker (portfolio import by ticker)

companies.ticker, indexé mais jamais unique : un même symbole peut désigner des sociétés
différentes sur plusieurs places — l'import de portefeuille marque alors la ligne AMBIGUOUS
(app/investor/importation.py). Nul pour l'existant.

Revision ID: 161f99c1f733
Revises: be63d4541f22
Create Date: 2026-10-01 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '161f99c1f733'
down_revision: str | Sequence[str] | None = 'be63d4541f22'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('companies', sa.Column('ticker', sa.String(length=20), nullable=True))
    op.create_index('ix_companies_ticker', 'companies', ['ticker'])


def downgrade() -> None:
    """Downgrade schema — les tickers renseignés sont perdus."""
    op.drop_index('ix_companies_ticker', table_name='companies')
    op.drop_column('companies', 'ticker')
