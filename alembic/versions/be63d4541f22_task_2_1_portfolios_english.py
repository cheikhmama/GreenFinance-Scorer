"""task 2.1: portfolios / portfolio_positions — English model, import-ready positions

Migration consolidée de la tâche 2.1 (docs/TASKS.md, glossaire docs/RENAME_PLAN.md §4) :

1. portefeuille -> portfolios, position_portefeuille -> portfolio_positions, colonnes, contraintes
   et index renommés.
2. portfolios : agrégats mis en cache (total_esg_score, waci, financed_emissions_tco2e,
   computed_at, config_hash), nuls tant que le moteur PCAF (tâche 2.3) ne les calcule pas.
3. portfolio_positions : identifier_type / identifier_raw / match_status / weight pour l'import
   par ISIN ou ticker (tâche 2.2). company_id devient nullable — une ligne importée que rien ne
   reconnaît est conservée (UNMATCHED / AMBIGUOUS), jamais écartée —, lié à match_status par
   ck_portfolio_positions_company_iff_matched. Les positions existantes sont MATCHED.
4. ON DELETE explicites : portfolios.user_id CASCADE (le portefeuille n'appartient qu'à son
   investisseur, docs/RENAME_PLAN.md §3.2 revu avec ce module), portfolio_positions.portfolio_id
   CASCADE (index ajouté).

Revision ID: be63d4541f22
Revises: fa4f8e80e840
Create Date: 2026-09-30 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'be63d4541f22'
down_revision: str | Sequence[str] | None = 'fa4f8e80e840'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = [('portefeuille', 'portfolios'), ('position_portefeuille', 'portfolio_positions')]
COLONNES = {
    'portfolios': [
        ('investisseur_id', 'user_id'),
        ('nom', 'name'),
        ('devise_reference', 'reference_currency'),
        ('date_creation', 'created_at'),
        ('archive', 'archived'),
    ],
    'portfolio_positions': [
        ('portefeuille_id', 'portfolio_id'),
        ('entreprise_id', 'company_id'),
        ('montant_investi', 'outstanding_amount'),
        ('devise', 'currency'),
        ('taux_change_utilise', 'fx_rate_used'),
        ('montant_converti', 'converted_amount'),
        ('type_duree', 'duration_type'),
        ('date_debut', 'start_date'),
        ('date_fin', 'end_date'),
    ],
}
CONTRAINTES_RENOMMEES = [
    ('portfolios', 'portefeuille_pkey', 'portfolios_pkey'),
    ('portfolio_positions', 'position_portefeuille_pkey', 'portfolio_positions_pkey'),
    ('portfolio_positions', 'ck_position_portefeuille_montant_positif',
     'ck_portfolio_positions_amount_positive'),
    ('portfolio_positions', 'position_portefeuille_entreprise_id_fkey',
     'portfolio_positions_company_id_fkey'),
]
INDEX_RENOMMES = [
    ('ix_portefeuille_investisseur_id', 'ix_portfolios_user_id'),
    ('ix_position_portefeuille_entreprise_id', 'ix_portfolio_positions_company_id'),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('portefeuille_investisseur_id_fkey', 'portefeuille', type_='foreignkey')
    op.drop_constraint(
        'position_portefeuille_portefeuille_id_fkey', 'position_portefeuille', type_='foreignkey'
    )
    for ancien, nouveau in TABLES:
        op.rename_table(ancien, nouveau)
    for table, colonnes in COLONNES.items():
        for ancien, nouveau in colonnes:
            op.alter_column(table, ancien, new_column_name=nouveau)
    for table, ancien, nouveau in CONTRAINTES_RENOMMEES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {ancien} TO {nouveau}')
    for ancien, nouveau in INDEX_RENOMMES:
        op.execute(f'ALTER INDEX {ancien} RENAME TO {nouveau}')

    # --- portfolios ---------------------------------------------------------------------------
    for colonne in ('total_esg_score', 'waci', 'financed_emissions_tco2e'):
        op.add_column('portfolios', sa.Column(colonne, sa.Float(), nullable=True))
    op.add_column('portfolios', sa.Column('computed_at', sa.DateTime(), nullable=True))
    op.add_column('portfolios', sa.Column('config_hash', sa.String(length=64), nullable=True))
    op.create_foreign_key(
        'portfolios_user_id_fkey', 'portfolios', 'users', ['user_id'], ['id'], ondelete='CASCADE'
    )

    # --- portfolio_positions ------------------------------------------------------------------
    op.add_column('portfolio_positions', sa.Column('identifier_type', sa.String(length=64), nullable=True))
    op.add_column('portfolio_positions', sa.Column('identifier_raw', sa.String(length=64), nullable=True))
    op.add_column('portfolio_positions', sa.Column(
        'match_status', sa.String(length=64), nullable=False, server_default='MATCHED'
    ))
    op.alter_column('portfolio_positions', 'match_status', server_default=None)
    op.add_column('portfolio_positions', sa.Column('weight', sa.Float(), nullable=True))
    op.alter_column('portfolio_positions', 'company_id', existing_type=sa.Uuid(), nullable=True)
    op.create_check_constraint(
        'ck_portfolio_positions_weight_range',
        'portfolio_positions',
        'weight IS NULL OR (weight > 0 AND weight <= 1)',
    )
    op.create_check_constraint(
        'ck_portfolio_positions_company_iff_matched',
        'portfolio_positions',
        "(match_status = 'MATCHED') = (company_id IS NOT NULL)",
    )
    op.create_foreign_key(
        'portfolio_positions_portfolio_id_fkey', 'portfolio_positions', 'portfolios',
        ['portfolio_id'], ['id'], ondelete='CASCADE',
    )
    op.create_index('ix_portfolio_positions_portfolio_id', 'portfolio_positions', ['portfolio_id'])


def downgrade() -> None:
    """Downgrade schema.

    Pertes assumées : les lignes non rapprochées (sans entreprise) ne peuvent pas exister dans
    l'ancien schéma et sont supprimées ; identifiants importés, poids et agrégats en cache sont
    perdus."""
    op.execute("DELETE FROM portfolio_positions WHERE company_id IS NULL")
    op.drop_index('ix_portfolio_positions_portfolio_id', table_name='portfolio_positions')
    op.drop_constraint('portfolio_positions_portfolio_id_fkey', 'portfolio_positions', type_='foreignkey')
    op.drop_constraint('ck_portfolio_positions_company_iff_matched', 'portfolio_positions', type_='check')
    op.drop_constraint('ck_portfolio_positions_weight_range', 'portfolio_positions', type_='check')
    op.alter_column('portfolio_positions', 'company_id', existing_type=sa.Uuid(), nullable=False)
    for colonne in ('weight', 'match_status', 'identifier_raw', 'identifier_type'):
        op.drop_column('portfolio_positions', colonne)

    op.drop_constraint('portfolios_user_id_fkey', 'portfolios', type_='foreignkey')
    for colonne in ('config_hash', 'computed_at', 'financed_emissions_tco2e', 'waci', 'total_esg_score'):
        op.drop_column('portfolios', colonne)

    for ancien, nouveau in INDEX_RENOMMES:
        op.execute(f'ALTER INDEX {nouveau} RENAME TO {ancien}')
    for table, ancien, nouveau in CONTRAINTES_RENOMMEES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {nouveau} TO {ancien}')
    for table, colonnes in COLONNES.items():
        for ancien, nouveau in colonnes:
            op.alter_column(table, nouveau, new_column_name=ancien)
    for ancien, nouveau in TABLES:
        op.rename_table(nouveau, ancien)

    op.create_foreign_key(
        'portefeuille_investisseur_id_fkey', 'portefeuille', 'users',
        ['investisseur_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'position_portefeuille_portefeuille_id_fkey', 'position_portefeuille', 'portefeuille',
        ['portefeuille_id'], ['id'],
    )
