"""task 1.1: company / ESG report / ESG metric — English domain model

Migration consolidée de la tâche 1.1 (docs/TASKS.md, glossaire docs/RENAME_PLAN.md §2) :

1. entreprise -> companies, rapport_esg -> esg_reports, indicateur_esg -> esg_metrics, avec leurs
   colonnes, contraintes et index renommés.
2. companies : `actif` remplacé par `status` (CompanyStatus) ; nouveaux champs ISIN, LEI,
   chiffre d'affaires et valeur d'entreprise (EVIC) pour PCAF.
3. esg_reports : l'ancien statut unique est découpé en `status` (ReportStatus, décision D2) et
   `extraction_status` (ExtractionStatus), données migrées dans les deux sens (§2.4) ;
   nouveaux champs official_score, coverage_rate, config_hash.
4. esg_metrics : unicité (report_id, metric_code) — la migration refuse de s'appliquer s'il existe
   déjà des doublons plutôt que d'en supprimer un arbitrairement ; champs de correction Auditeur.
5. Toute clé étrangère vers ou depuis ces trois tables reçoit une règle ON DELETE explicite et un
   index sur la colonne référençante (§2.5).

Revision ID: 21e17187789f
Revises: 0c09f23a93cb
Create Date: 2026-09-29 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '21e17187789f'
down_revision: str | Sequence[str] | None = '0c09f23a93cb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = [
    ('entreprise', 'companies'),
    ('rapport_esg', 'esg_reports'),
    ('indicateur_esg', 'esg_metrics'),
]

COLONNES = {
    'companies': [
        ('nom', 'name'),
        ('secteur', 'sector'),
        ('pays', 'country'),
        ('site_officiel', 'website'),
        ('utilisateur_id', 'owner_user_id'),
        ('montant_minimum_investissement', 'minimum_investment_amount'),
        ('devise_montant_minimum', 'minimum_investment_currency'),
        ('date_publication', 'published_at'),
    ],
    'esg_reports': [
        ('entreprise_id', 'company_id'),
        ('canal', 'channel'),
        ('date_depot', 'submitted_at'),
        ('statut', 'status'),
        ('fichier_source', 'source_file'),
        ('nom_fichier_origine', 'original_filename'),
        ('annee_reporting', 'fiscal_year'),
        ('auditeur_id', 'auditor_id'),
        ('date_affectation', 'assigned_at'),
        ('extraction_demarree_le', 'extraction_started_at'),
        ('extraction_terminee_le', 'extraction_finished_at'),
        ('extraction_erreur', 'extraction_error'),
        ('tentatives_extraction', 'extraction_attempts'),
        ('rapport_precedent_id', 'previous_report_id'),
        ('score_global_declare', 'declared_global_score'),
        ('score_global_declare_preuve_id', 'declared_global_score_proof_id'),
        ('rapport_synthese_genere', 'synthesis_report_path'),
    ],
    'esg_metrics': [
        ('rapport_id', 'report_id'),
        ('pilier', 'pillar'),
        ('code', 'metric_code'),
        ('valeur', 'value'),
        ('unite', 'unit'),
        ('methode', 'method'),
        ('preuve_id', 'proof_id'),
        ('valeur_brute', 'raw_value'),
        ('citation_source', 'proof_text'),
        ('annee_valeur', 'value_year'),
        ('confiance', 'confidence'),
    ],
}

# Contraintes/index existants renommés avec leur table : (table cible, ancien nom, nouveau nom).
CONTRAINTES_RENOMMEES = [
    ('companies', 'entreprise_pkey', 'companies_pkey'),
    ('esg_reports', 'rapport_esg_pkey', 'esg_reports_pkey'),
    ('esg_reports', 'uq_rapport_esg_entreprise_checksum', 'uq_esg_reports_company_checksum'),
    ('esg_metrics', 'indicateur_esg_pkey', 'esg_metrics_pkey'),
]
INDEX_RENOMMES = [
    ('ix_rapport_esg_checksum_sha256', 'ix_esg_reports_checksum_sha256'),
]

# Clés étrangères reconstruites avec une règle ON DELETE explicite :
# (table, colonne, table référencée, ancien nom (avant migration), nouveau nom, ON DELETE).
# L'application ne supprime jamais une entreprise ni un rapport (suspension et versioning sont
# les opérations applicatives) : ces règles définissent ce qu'une purge administrative emporte.
CLES_ETRANGERES = [
    ('companies', 'owner_user_id', 'utilisateur',
     'entreprise_utilisateur_id_fkey', 'companies_owner_user_id_fkey', 'SET NULL'),
    ('esg_reports', 'company_id', 'companies',
     'rapport_esg_entreprise_id_fkey', 'esg_reports_company_id_fkey', 'CASCADE'),
    ('esg_reports', 'auditor_id', 'utilisateur',
     'rapport_esg_auditeur_id_fkey', 'esg_reports_auditor_id_fkey', 'SET NULL'),
    ('esg_reports', 'previous_report_id', 'esg_reports',
     'fk_rapport_esg_rapport_precedent_id_rapport_esg', 'esg_reports_previous_report_id_fkey',
     'SET NULL'),
    ('esg_reports', 'declared_global_score_proof_id', 'preuve_documentaire',
     'rapport_esg_score_global_declare_preuve_id_fkey',
     'esg_reports_declared_global_score_proof_id_fkey', 'SET NULL'),
    ('esg_metrics', 'report_id', 'esg_reports',
     'indicateur_esg_rapport_id_fkey', 'esg_metrics_report_id_fkey', 'CASCADE'),
    ('esg_metrics', 'proof_id', 'preuve_documentaire',
     'indicateur_esg_preuve_id_fkey', 'esg_metrics_proof_id_fkey', 'CASCADE'),
    # Clés entrantes : colonnes non renommées avant la tâche de leur propre module (§1, règle 2).
    ('analyse_entreprise', 'entreprise_id', 'companies',
     'analyse_entreprise_entreprise_id_fkey', 'analyse_entreprise_entreprise_id_fkey', 'CASCADE'),
    ('analyse_entreprise', 'rapport_id', 'esg_reports',
     'fk_analyse_entreprise_rapport_id_rapport_esg', 'analyse_entreprise_rapport_id_fkey',
     'SET NULL'),
    ('avis_audit', 'rapport_id', 'esg_reports',
     'avis_audit_rapport_id_fkey', 'avis_audit_rapport_id_fkey', 'CASCADE'),
    ('couverture_indicateur', 'rapport_id', 'esg_reports',
     'couverture_indicateur_rapport_id_fkey', 'couverture_indicateur_rapport_id_fkey', 'CASCADE'),
    ('donnee_carbone', 'rapport_id', 'esg_reports',
     'donnee_carbone_rapport_id_fkey', 'donnee_carbone_rapport_id_fkey', 'CASCADE'),
    ('position_portefeuille', 'entreprise_id', 'companies',
     'position_portefeuille_entreprise_id_fkey', 'position_portefeuille_entreprise_id_fkey',
     'CASCADE'),
    ('projet_document', 'rapport_id', 'esg_reports',
     'projet_document_rapport_id_fkey', 'projet_document_rapport_id_fkey', 'CASCADE'),
    ('projet_entreprise', 'entreprise_id', 'companies',
     'projet_entreprise_entreprise_id_fkey', 'projet_entreprise_entreprise_id_fkey', 'CASCADE'),
    ('score_esg', 'rapport_id', 'esg_reports',
     'score_esg_rapport_id_fkey', 'score_esg_rapport_id_fkey', 'CASCADE'),
    ('signalement_ecart', 'entreprise_id', 'companies',
     'signalement_ecart_entreprise_id_fkey', 'signalement_ecart_entreprise_id_fkey', 'CASCADE'),
    ('signalement_ecart', 'indicateur_id', 'esg_metrics',
     'signalement_ecart_indicateur_id_fkey', 'signalement_ecart_indicateur_id_fkey', 'CASCADE'),
]

# Index sur les colonnes référençantes qui n'en avaient pas (ceux déjà couverts par un index
# composite commençant par la colonne — score_esg, couverture_indicateur, esg_metrics.report_id,
# esg_reports.company_id — n'en reçoivent pas de redondant).
INDEX_AJOUTES = [
    ('companies', 'owner_user_id'),
    ('esg_reports', 'auditor_id'),
    ('esg_reports', 'previous_report_id'),
    ('esg_reports', 'declared_global_score_proof_id'),
    ('esg_metrics', 'proof_id'),
    ('analyse_entreprise', 'entreprise_id'),
    ('analyse_entreprise', 'rapport_id'),
    ('avis_audit', 'rapport_id'),
    ('donnee_carbone', 'rapport_id'),
    ('position_portefeuille', 'entreprise_id'),
    ('projet_document', 'rapport_id'),
    ('projet_entreprise', 'entreprise_id'),
    ('signalement_ecart', 'entreprise_id'),
    ('signalement_ecart', 'indicateur_id'),
]

# ReportStatus <- StatutRapport (docs/RENAME_PLAN.md §2.4).
STATUT_VERS_STATUS = {
    'ENVOYE': 'SUBMITTED',
    'EN_EXTRACTION': 'SUBMITTED',
    'AFFECTE_AUDITEUR': 'PENDING_AUDIT',
    'EN_VALIDATION': 'PENDING_DECISION',
    'DEMANDE_CORRECTION': 'REVISION_REQUESTED',
    'VALIDE': 'VALIDATED',
    'REJETE': 'REJECTED',
}


def _case(colonne: str, correspondances: dict[str, str]) -> str:
    branches = ' '.join(f"WHEN '{avant}' THEN '{apres}'" for avant, apres in correspondances.items())
    return f'CASE {colonne} {branches} END'


def upgrade() -> None:
    """Upgrade schema."""
    connexion = op.get_bind()

    # Garde-fou : jamais de suppression arbitraire d'un point de donnée extrait.
    doublons = connexion.execute(sa.text(
        'SELECT rapport_id, code, count(*) FROM indicateur_esg '
        'GROUP BY rapport_id, code HAVING count(*) > 1 LIMIT 10'
    )).fetchall()
    if doublons:
        raise RuntimeError(
            'indicateur_esg contient des doublons (rapport_id, code) : '
            f'{[(str(r), c, n) for r, c, n in doublons]} — relancer l\'extraction de ces '
            'rapports (qui dédoublonne désormais) avant d\'appliquer cette migration.'
        )

    for table, _colonne, _ref, ancien, _nouveau, _regle in CLES_ETRANGERES:
        # Noms d'avant renommage : la table référençante peut encore porter son ancien nom.
        table_actuelle = {n: a for a, n in TABLES}.get(table, table)
        op.drop_constraint(ancien, table_actuelle, type_='foreignkey')

    for ancien, nouveau in TABLES:
        op.rename_table(ancien, nouveau)
    for table, colonnes in COLONNES.items():
        for ancien, nouveau in colonnes:
            op.alter_column(table, ancien, new_column_name=nouveau)
    for table, ancien, nouveau in CONTRAINTES_RENOMMEES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {ancien} TO {nouveau}')
    for ancien, nouveau in INDEX_RENOMMES:
        op.execute(f'ALTER INDEX {ancien} RENAME TO {nouveau}')

    # --- companies -------------------------------------------------------------------------
    op.add_column('companies', sa.Column(
        'status', sa.String(length=64), nullable=False, server_default='ACTIVE'
    ))
    op.execute("UPDATE companies SET status = CASE WHEN actif THEN 'ACTIVE' ELSE 'SUSPENDED' END")
    op.alter_column('companies', 'status', server_default=None)
    op.drop_column('companies', 'actif')
    op.add_column('companies', sa.Column('isin', sa.String(length=12), nullable=True))
    op.add_column('companies', sa.Column('lei', sa.String(length=20), nullable=True))
    op.add_column('companies', sa.Column('revenue', sa.Numeric(20, 2), nullable=True))
    op.add_column('companies', sa.Column('revenue_currency', sa.String(length=64), nullable=True))
    op.add_column('companies', sa.Column('enterprise_value', sa.Numeric(20, 2), nullable=True))
    op.add_column('companies', sa.Column(
        'enterprise_value_currency', sa.String(length=64), nullable=True
    ))
    op.add_column('companies', sa.Column('enterprise_value_as_of', sa.Date(), nullable=True))
    op.create_unique_constraint('companies_isin_key', 'companies', ['isin'])
    op.create_unique_constraint('companies_lei_key', 'companies', ['lei'])

    # --- esg_reports -----------------------------------------------------------------------
    op.add_column('esg_reports', sa.Column(
        'extraction_status', sa.String(length=64), nullable=False, server_default='NOT_STARTED'
    ))
    # Avancement déduit des horodatages existants, quel que soit l'ancien statut ; à défaut
    # d'horodatage, QUEUED pour un rapport encore en attente d'extraction (§2.4).
    op.execute("""
        UPDATE esg_reports SET extraction_status = CASE
            WHEN extraction_error IS NOT NULL THEN 'FAILED'
            WHEN extraction_finished_at IS NOT NULL THEN 'DONE'
            WHEN extraction_started_at IS NOT NULL THEN 'RUNNING'
            WHEN status IN ('ENVOYE', 'EN_EXTRACTION') THEN 'QUEUED'
            ELSE 'NOT_STARTED'
        END
    """)
    op.alter_column('esg_reports', 'extraction_status', server_default=None)
    op.execute(f"UPDATE esg_reports SET status = {_case('status', STATUT_VERS_STATUS)}")
    op.add_column('esg_reports', sa.Column('official_score', sa.Float(), nullable=True))
    op.add_column('esg_reports', sa.Column('coverage_rate', sa.Float(), nullable=True))
    op.add_column('esg_reports', sa.Column('config_hash', sa.String(length=64), nullable=True))
    op.create_index(
        'ix_esg_reports_company_fiscal_year', 'esg_reports', ['company_id', 'fiscal_year']
    )

    # --- esg_metrics -----------------------------------------------------------------------
    op.add_column('esg_metrics', sa.Column(
        'auditor_overridden', sa.Boolean(), nullable=False, server_default=sa.false()
    ))
    op.alter_column('esg_metrics', 'auditor_overridden', server_default=None)
    op.add_column('esg_metrics', sa.Column('override_value', sa.Float(), nullable=True))
    op.add_column('esg_metrics', sa.Column('override_reason', sa.String(), nullable=True))
    op.add_column('esg_metrics', sa.Column('overridden_by_id', sa.Uuid(), nullable=True))
    op.add_column('esg_metrics', sa.Column('overridden_at', sa.DateTime(), nullable=True))
    op.create_unique_constraint(
        'uq_esg_metrics_report_metric_code', 'esg_metrics', ['report_id', 'metric_code']
    )
    op.create_foreign_key(
        'esg_metrics_overridden_by_id_fkey', 'esg_metrics', 'utilisateur',
        ['overridden_by_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_esg_metrics_overridden_by_id', 'esg_metrics', ['overridden_by_id'])

    # --- clés étrangères et index ----------------------------------------------------------
    for table, colonne, ref, _ancien, nouveau, regle in CLES_ETRANGERES:
        op.create_foreign_key(nouveau, table, ref, [colonne], ['id'], ondelete=regle)
    for table, colonne in INDEX_AJOUTES:
        op.create_index(f'ix_{table}_{colonne}', table, [colonne])


def downgrade() -> None:
    """Downgrade schema — rétablit noms, valeurs et contraintes d'avant la tâche 1.1.

    Pertes assumées : les champs ajoutés (ISIN, LEI, données financières, correction Auditeur,
    official_score, coverage_rate, config_hash) sont supprimés ; DRAFT redevient ENVOYE,
    PENDING_ONBOARDING redevient une entreprise active (`actif` n'a que deux états), et un ancien
    EN_EXTRACTION sans aucun horodatage d'extraction (données antérieures à la Phase 6), passé
    QUEUED à la montée, redescend en ENVOYE — même sens, l'extraction n'avait jamais démarré."""
    for table, colonne in INDEX_AJOUTES:
        op.drop_index(f'ix_{table}_{colonne}', table_name=table)
    for table, _colonne, _ref, _ancien, nouveau, _regle in CLES_ETRANGERES:
        op.drop_constraint(nouveau, table, type_='foreignkey')

    # --- esg_metrics -----------------------------------------------------------------------
    op.drop_index('ix_esg_metrics_overridden_by_id', table_name='esg_metrics')
    op.drop_constraint('esg_metrics_overridden_by_id_fkey', 'esg_metrics', type_='foreignkey')
    op.drop_constraint('uq_esg_metrics_report_metric_code', 'esg_metrics', type_='unique')
    for colonne in (
        'overridden_at', 'overridden_by_id', 'override_reason', 'override_value',
        'auditor_overridden',
    ):
        op.drop_column('esg_metrics', colonne)

    # --- esg_reports -----------------------------------------------------------------------
    op.drop_index('ix_esg_reports_company_fiscal_year', table_name='esg_reports')
    for colonne in ('config_hash', 'coverage_rate', 'official_score'):
        op.drop_column('esg_reports', colonne)
    op.execute("""
        UPDATE esg_reports SET status = CASE status
            WHEN 'DRAFT' THEN 'ENVOYE'
            WHEN 'SUBMITTED' THEN CASE
                WHEN extraction_status IN ('QUEUED', 'NOT_STARTED') THEN 'ENVOYE'
                ELSE 'EN_EXTRACTION'
            END
            WHEN 'PENDING_AUDIT' THEN 'AFFECTE_AUDITEUR'
            WHEN 'PENDING_DECISION' THEN 'EN_VALIDATION'
            WHEN 'REVISION_REQUESTED' THEN 'DEMANDE_CORRECTION'
            WHEN 'VALIDATED' THEN 'VALIDE'
            WHEN 'REJECTED' THEN 'REJETE'
        END
    """)
    op.drop_column('esg_reports', 'extraction_status')

    # --- companies -------------------------------------------------------------------------
    op.drop_constraint('companies_lei_key', 'companies', type_='unique')
    op.drop_constraint('companies_isin_key', 'companies', type_='unique')
    for colonne in (
        'enterprise_value_as_of', 'enterprise_value_currency', 'enterprise_value',
        'revenue_currency', 'revenue', 'lei', 'isin',
    ):
        op.drop_column('companies', colonne)
    op.add_column('companies', sa.Column(
        'actif', sa.Boolean(), nullable=False, server_default=sa.true()
    ))
    op.execute("UPDATE companies SET actif = (status <> 'SUSPENDED')")
    op.alter_column('companies', 'actif', server_default=None)
    op.drop_column('companies', 'status')

    # --- noms --------------------------------------------------------------------------------
    for ancien, nouveau in INDEX_RENOMMES:
        op.execute(f'ALTER INDEX {nouveau} RENAME TO {ancien}')
    for table, ancien, nouveau in CONTRAINTES_RENOMMEES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {nouveau} TO {ancien}')
    for table, colonnes in COLONNES.items():
        for ancien, nouveau in colonnes:
            op.alter_column(table, nouveau, new_column_name=ancien)
    for ancien, nouveau in TABLES:
        op.rename_table(nouveau, ancien)

    # Clés étrangères d'origine, sans règle ON DELETE, sous leurs noms d'origine.
    anciens_noms_tables = {n: a for a, n in TABLES}
    colonnes_anciennes = {
        (table, nouveau): ancien
        for table, colonnes in COLONNES.items() for ancien, nouveau in colonnes
    }
    for table, colonne, ref, ancien, _nouveau, _regle in CLES_ETRANGERES:
        op.create_foreign_key(
            ancien,
            anciens_noms_tables.get(table, table),
            anciens_noms_tables.get(ref, ref),
            [colonnes_anciennes.get((table, colonne), colonne)],
            ['id'],
        )
