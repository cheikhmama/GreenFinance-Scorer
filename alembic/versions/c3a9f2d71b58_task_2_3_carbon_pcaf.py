"""task 2.3: carbon / evidence tables in English, PCAF data quality, Decimal amounts

Migration consolidée de la tâche 2.3 (docs/TASKS.md, glossaire docs/RENAME_PLAN.md §4) :

1. donnee_carbone -> carbon_emissions, preuve_documentaire -> evidence, couverture_indicateur ->
   metric_coverage, signalement_ecart -> discrepancy_flags : colonnes, contraintes et index
   renommés (les CHECK suivent les colonnes renommées, PostgreSQL les référence par numéro).
2. carbon_emissions.proof_id : ON DELETE CASCADE explicite (aucun jusqu'ici) + index, comme
   esg_metrics.proof_id.
3. carbon_emissions.pcaf_data_quality devient nullable, et le placeholder 3 écrit sur chaque ligne
   par l'ancien extracteur est remplacé par la qualité dérivée de la méthode (app/carbon/pcaf.py::
   qualite_donnee_pcaf) : RAPPORTEE 2, CALCULEE 3, ESTIMEE 4.
4. Montants en Decimal : portfolio_positions.outstanding_amount / converted_amount et
   companies.minimum_investment_amount en numeric(20,2), fx_rate_used en numeric(20,10), weight en
   numeric(11,10). Les valeurs existantes sont arrondies au centime.

Revision ID: c3a9f2d71b58
Revises: 161f99c1f733
Create Date: 2026-10-02 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3a9f2d71b58'
down_revision: str | Sequence[str] | None = '161f99c1f733'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = [
    ('preuve_documentaire', 'evidence'),
    ('donnee_carbone', 'carbon_emissions'),
    ('couverture_indicateur', 'metric_coverage'),
    ('signalement_ecart', 'discrepancy_flags'),
]
COLONNES = {
    'evidence': [
        ('nom_document', 'document_name'),
        ('annee', 'year'),
        ('nombre_pages_total', 'total_pages'),
        ('page_debut', 'page_start'),
        ('page_fin', 'page_end'),
        ('pdf_extrait_genere', 'excerpt_pdf_path'),
    ],
    'carbon_emissions': [
        ('rapport_id', 'report_id'),
        ('categorie_ges', 'ghg_category'),
        ('valeur_tonnes_co2e', 'tonnes_co2e'),
        ('annee', 'year'),
        ('methode', 'method'),
        ('score_qualite_pcaf', 'pcaf_data_quality'),
        ('preuve_id', 'proof_id'),
        ('valeur_brute', 'raw_value'),
        ('citation_source', 'proof_text'),
        ('annee_valeur', 'value_year'),
        ('confiance', 'confidence'),
    ],
    'metric_coverage': [
        ('rapport_id', 'report_id'),
        ('code', 'metric_code'),
        ('statut', 'status'),
        ('pages_examinees', 'pages_examined'),
    ],
    'discrepancy_flags': [
        ('indicateur_id', 'metric_id'),
        ('entreprise_id', 'company_id'),
        ('nature_ecart', 'nature'),
        ('statut', 'status'),
        ('date_signalement', 'flagged_at'),
    ],
}
CONTRAINTES_RENOMMEES = [
    ('evidence', 'preuve_documentaire_pkey', 'evidence_pkey'),
    ('carbon_emissions', 'donnee_carbone_pkey', 'carbon_emissions_pkey'),
    ('carbon_emissions', 'donnee_carbone_rapport_id_fkey', 'carbon_emissions_report_id_fkey'),
    ('carbon_emissions', 'ck_donnee_carbone_scope_valide', 'ck_carbon_emissions_scope'),
    ('carbon_emissions', 'ck_donnee_carbone_pcaf_borne',
     'ck_carbon_emissions_pcaf_data_quality_range'),
    ('carbon_emissions', 'ck_donnee_carbone_valeur_non_negative',
     'ck_carbon_emissions_tonnes_non_negative'),
    ('metric_coverage', 'couverture_indicateur_pkey', 'metric_coverage_pkey'),
    ('metric_coverage', 'couverture_indicateur_rapport_id_fkey', 'metric_coverage_report_id_fkey'),
    ('metric_coverage', 'uq_couverture_indicateur_rapport_code',
     'uq_metric_coverage_report_metric_code'),
    ('discrepancy_flags', 'signalement_ecart_pkey', 'discrepancy_flags_pkey'),
    ('discrepancy_flags', 'signalement_ecart_indicateur_id_fkey', 'discrepancy_flags_metric_id_fkey'),
    ('discrepancy_flags', 'signalement_ecart_entreprise_id_fkey',
     'discrepancy_flags_company_id_fkey'),
]
INDEX_RENOMMES = [
    ('ix_donnee_carbone_rapport_id', 'ix_carbon_emissions_report_id'),
    ('ix_signalement_ecart_indicateur_id', 'ix_discrepancy_flags_metric_id'),
    ('ix_signalement_ecart_entreprise_id', 'ix_discrepancy_flags_company_id'),
]
# (table, colonne, type numeric, nullable)
MONTANTS = [
    ('portfolio_positions', 'outstanding_amount', sa.Numeric(20, 2), False),
    ('portfolio_positions', 'converted_amount', sa.Numeric(20, 2), False),
    ('portfolio_positions', 'fx_rate_used', sa.Numeric(20, 10), True),
    ('portfolio_positions', 'weight', sa.Numeric(11, 10), True),
    ('companies', 'minimum_investment_amount', sa.Numeric(20, 2), True),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('donnee_carbone_preuve_id_fkey', 'donnee_carbone', type_='foreignkey')
    for ancien, nouveau in TABLES:
        op.rename_table(ancien, nouveau)
    for table, colonnes in COLONNES.items():
        for ancien, nouveau in colonnes:
            op.alter_column(table, ancien, new_column_name=nouveau)
    for table, ancien, nouveau in CONTRAINTES_RENOMMEES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {ancien} TO {nouveau}')
    for ancien, nouveau in INDEX_RENOMMES:
        op.execute(f'ALTER INDEX {ancien} RENAME TO {nouveau}')

    op.create_foreign_key(
        'carbon_emissions_proof_id_fkey', 'carbon_emissions', 'evidence',
        ['proof_id'], ['id'], ondelete='CASCADE',
    )
    op.create_index('ix_carbon_emissions_proof_id', 'carbon_emissions', ['proof_id'])

    op.alter_column(
        'carbon_emissions', 'pcaf_data_quality', existing_type=sa.Integer(), nullable=True
    )
    op.execute(
        "UPDATE carbon_emissions SET pcaf_data_quality = CASE method "
        "WHEN 'RAPPORTEE' THEN 2 WHEN 'CALCULEE' THEN 3 WHEN 'ESTIMEE' THEN 4 END"
    )

    for table, colonne, type_, nullable in MONTANTS:
        op.alter_column(
            table, colonne, existing_type=sa.Float(), type_=type_, existing_nullable=nullable,
            postgresql_using=f'round({colonne}::numeric, {type_.scale})',
        )


def downgrade() -> None:
    """Downgrade schema.

    Perte assumée : la qualité PCAF dérivée redevient le placeholder 3 que l'ancien extracteur
    écrivait sur chaque ligne (l'ancien schéma l'exige non nul). Les montants redeviennent des
    float (valeurs conservées, arrondies au centime par l'upgrade)."""
    for table, colonne, type_, nullable in MONTANTS:
        op.alter_column(
            table, colonne, existing_type=type_, type_=sa.Float(), existing_nullable=nullable,
            postgresql_using=f'{colonne}::double precision',
        )

    op.execute("UPDATE carbon_emissions SET pcaf_data_quality = 3")
    op.alter_column(
        'carbon_emissions', 'pcaf_data_quality', existing_type=sa.Integer(), nullable=False
    )

    op.drop_index('ix_carbon_emissions_proof_id', table_name='carbon_emissions')
    op.drop_constraint('carbon_emissions_proof_id_fkey', 'carbon_emissions', type_='foreignkey')

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
        'donnee_carbone_preuve_id_fkey', 'donnee_carbone', 'preuve_documentaire',
        ['preuve_id'], ['id'],
    )
