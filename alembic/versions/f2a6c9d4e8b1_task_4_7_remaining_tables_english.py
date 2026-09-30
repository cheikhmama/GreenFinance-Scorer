"""task 4.7: remaining tables in English (audit, researcher, institution, core, auth)

Dernier renommage de persistance (docs/RENAME_PLAN.md §3e) : avis_audit, journal_audit,
notification, institution_profil, chercheur_institution, analyse, analyse_entreprise, projet,
affectation_projet, projet_entreprise, projet_document — tables, colonnes, contraintes, index.

Clés étrangères sans règle jusqu'ici, rendues explicites (docs/RENAME_PLAN.md §1 règle 5) :
- analyses.project_id RESTRICT (une analyse est un travail rendu) + index ;
- analyses.previous_analysis_id SET NULL + index ;
- analysis_companies.analysis_id, project_assignments / project_companies /
  project_documents.project_id CASCADE (index : l'unicité qui les porte en tête).

Journal d'audit : actions, types de ressource et résultats passent en anglais (ex. connexion ->
login, Utilisateur -> User, succes -> success, actif -> active), dans les deux sens.

Revision ID: f2a6c9d4e8b1
Revises: d5b8e1f0a3c7
Create Date: 2026-10-06 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f2a6c9d4e8b1'
down_revision: str | Sequence[str] | None = 'd5b8e1f0a3c7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (ancienne table, nouvelle table, [(ancienne colonne, nouvelle colonne)])
TABLES = [
    ('avis_audit', 'audit_opinions', [
        ('rapport_id', 'report_id'), ('auditeur_id', 'auditor_id'), ('commentaire', 'comment'),
        ('date_avis', 'submitted_at'),
    ]),
    ('journal_audit', 'audit_log', [
        ('acteur_id', 'actor_id'), ('type_ressource', 'resource_type'),
        ('id_ressource', 'resource_id'), ('date', 'occurred_at'), ('resultat', 'result'),
        ('ancienne_valeur', 'old_value'), ('nouvelle_valeur', 'new_value'),
    ]),
    ('notification', 'notifications', [
        ('utilisateur_id', 'user_id'), ('id_ressource', 'resource_id'), ('date_envoi', 'sent_at'),
        ('lu', 'read'),
    ]),
    ('institution_profil', 'institution_profiles', [
        ('utilisateur_id', 'user_id'), ('quota_export', 'export_quota'),
    ]),
    ('chercheur_institution', 'researcher_affiliations', [
        ('chercheur_id', 'researcher_id'), ('statut', 'status'), ('date_invitation', 'invited_at'),
        ('date_reponse', 'responded_at'), ('conditions_collaboration', 'collaboration_terms'),
    ]),
    ('analyse', 'analyses', [
        ('projet_id', 'project_id'), ('chercheur_id', 'researcher_id'), ('titre', 'title'),
        ('contenu', 'content'), ('statut', 'status'),
        ('analyse_precedente_id', 'previous_analysis_id'),
        ('commentaire_institution', 'institution_comment'), ('date_creation', 'created_at'),
        ('date_soumission', 'submitted_at'), ('date_decision', 'decided_at'),
    ]),
    ('analyse_entreprise', 'analysis_companies', [
        ('analyse_id', 'analysis_id'), ('entreprise_id', 'company_id'), ('rapport_id', 'report_id'),
        ('score_esg_id', 'score_id'),
    ]),
    ('projet', 'projects', [
        ('nom', 'name'), ('objectif', 'objective'), ('date_debut', 'start_date'),
        ('date_fin_prevue', 'planned_end_date'), ('date_limite', 'deadline'), ('statut', 'status'),
        ('date_creation', 'created_at'), ('date_cloture', 'closed_at'),
    ]),
    ('affectation_projet', 'project_assignments', [
        ('projet_id', 'project_id'), ('chercheur_id', 'researcher_id'),
        ('date_affectation', 'assigned_at'),
    ]),
    ('projet_entreprise', 'project_companies', [
        ('projet_id', 'project_id'), ('entreprise_id', 'company_id'), ('date_ajout', 'added_at'),
    ]),
    ('projet_document', 'project_documents', [
        ('projet_id', 'project_id'), ('rapport_id', 'report_id'), ('date_ajout', 'added_at'),
    ]),
]

# (table après renommage, ancien nom, nouveau nom) — contraintes conservées telles quelles.
CONTRAINTES = [
    ('audit_opinions', 'avis_audit_pkey', 'audit_opinions_pkey'),
    ('audit_opinions', 'avis_audit_rapport_id_fkey', 'audit_opinions_report_id_fkey'),
    ('audit_opinions', 'avis_audit_auditeur_id_fkey', 'audit_opinions_auditor_id_fkey'),
    ('audit_log', 'journal_audit_pkey', 'audit_log_pkey'),
    ('audit_log', 'journal_audit_acteur_id_fkey', 'audit_log_actor_id_fkey'),
    ('notifications', 'notification_pkey', 'notifications_pkey'),
    ('notifications', 'notification_utilisateur_id_fkey', 'notifications_user_id_fkey'),
    ('institution_profiles', 'institution_profil_pkey', 'institution_profiles_pkey'),
    ('institution_profiles', 'institution_profil_utilisateur_id_fkey',
     'institution_profiles_user_id_fkey'),
    ('institution_profiles', 'institution_profil_utilisateur_id_key',
     'institution_profiles_user_id_key'),
    ('researcher_affiliations', 'chercheur_institution_pkey', 'researcher_affiliations_pkey'),
    ('researcher_affiliations', 'chercheur_institution_chercheur_id_fkey',
     'researcher_affiliations_researcher_id_fkey'),
    ('researcher_affiliations', 'chercheur_institution_institution_id_fkey',
     'researcher_affiliations_institution_id_fkey'),
    ('researcher_affiliations', 'uq_chercheur_institution',
     'uq_researcher_affiliations_researcher_institution'),
    ('analyses', 'analyse_pkey', 'analyses_pkey'),
    ('analyses', 'analyse_chercheur_id_fkey', 'analyses_researcher_id_fkey'),
    ('analysis_companies', 'analyse_entreprise_pkey', 'analysis_companies_pkey'),
    ('analysis_companies', 'analyse_entreprise_entreprise_id_fkey',
     'analysis_companies_company_id_fkey'),
    ('analysis_companies', 'analyse_entreprise_rapport_id_fkey', 'analysis_companies_report_id_fkey'),
    ('analysis_companies', 'fk_analyse_entreprise_score_esg_id_scores',
     'analysis_companies_score_id_fkey'),
    ('analysis_companies', 'uq_analyse_entreprise', 'uq_analysis_companies_analysis_company'),
    ('projects', 'projet_pkey', 'projects_pkey'),
    ('projects', 'projet_institution_id_fkey', 'projects_institution_id_fkey'),
    ('project_assignments', 'affectation_projet_pkey', 'project_assignments_pkey'),
    ('project_assignments', 'affectation_projet_chercheur_id_fkey',
     'project_assignments_researcher_id_fkey'),
    ('project_assignments', 'uq_affectation_projet_chercheur',
     'uq_project_assignments_project_researcher'),
    ('project_companies', 'projet_entreprise_pkey', 'project_companies_pkey'),
    ('project_companies', 'projet_entreprise_entreprise_id_fkey',
     'project_companies_company_id_fkey'),
    ('project_companies', 'uq_projet_entreprise', 'uq_project_companies_project_company'),
    ('project_documents', 'projet_document_pkey', 'project_documents_pkey'),
    ('project_documents', 'projet_document_rapport_id_fkey', 'project_documents_report_id_fkey'),
    ('project_documents', 'uq_projet_document', 'uq_project_documents_project_report'),
]

INDEX = [
    ('ix_avis_audit_auditeur_id', 'ix_audit_opinions_auditor_id'),
    ('ix_avis_audit_rapport_id', 'ix_audit_opinions_report_id'),
    ('ix_journal_audit_acteur_id', 'ix_audit_log_actor_id'),
    ('ix_notification_utilisateur_id', 'ix_notifications_user_id'),
    ('ix_chercheur_institution_institution_id', 'ix_researcher_affiliations_institution_id'),
    ('ix_analyse_chercheur_id', 'ix_analyses_researcher_id'),
    ('ix_analyse_entreprise_entreprise_id', 'ix_analysis_companies_company_id'),
    ('ix_analyse_entreprise_rapport_id', 'ix_analysis_companies_report_id'),
    ('ix_analyse_entreprise_score_esg_id', 'ix_analysis_companies_score_id'),
    ('ix_projet_institution_id', 'ix_projects_institution_id'),
    ('ix_affectation_projet_chercheur_id', 'ix_project_assignments_researcher_id'),
    ('ix_projet_entreprise_entreprise_id', 'ix_project_companies_company_id'),
    ('ix_projet_document_rapport_id', 'ix_project_documents_report_id'),
]

# (table, colonne, table cible, ancien nom de contrainte, nouveau nom, règle nouvelle)
CLES_SANS_REGLE = [
    ('analyses', 'project_id', 'projects', 'analyse_projet_id_fkey',
     'analyses_project_id_fkey', 'RESTRICT'),
    ('analyses', 'previous_analysis_id', 'analyses', 'analyse_analyse_precedente_id_fkey',
     'analyses_previous_analysis_id_fkey', 'SET NULL'),
    ('analysis_companies', 'analysis_id', 'analyses', 'analyse_entreprise_analyse_id_fkey',
     'analysis_companies_analysis_id_fkey', 'CASCADE'),
    ('project_assignments', 'project_id', 'projects', 'affectation_projet_projet_id_fkey',
     'project_assignments_project_id_fkey', 'CASCADE'),
    ('project_companies', 'project_id', 'projects', 'projet_entreprise_projet_id_fkey',
     'project_companies_project_id_fkey', 'CASCADE'),
    ('project_documents', 'project_id', 'projects', 'projet_document_projet_id_fkey',
     'project_documents_project_id_fkey', 'CASCADE'),
]
NOUVEAUX_INDEX = [
    ('ix_analyses_project_id', 'analyses', 'project_id'),
    ('ix_analyses_previous_analysis_id', 'analyses', 'previous_analysis_id'),
]

# Journal d'audit : valeurs français -> anglais, par colonne.
VALEURS_JOURNAL = {
    'action': {
        'activation_compte': 'account_activated',
        'changement_mot_de_passe': 'password_changed',
        'changement_role': 'role_changed',
        'connexion': 'login',
        'creation_compte': 'account_created',
        'deconnexion': 'logout',
        'demande_changement_email': 'email_change_requested',
        'demande_reinitialisation_mot_de_passe': 'password_reset_requested',
        'desactivation_compte': 'account_deactivated',
        'inscription_entreprise': 'company_registered',
        'modification_email': 'email_changed',
        'reactivation_compte': 'account_reactivated',
        'refus_inscription': 'registration_rejected',
        'reinitialisation_mot_de_passe': 'password_reset',
        'renvoi_lien_activation': 'activation_link_resent',
        'validation_inscription': 'registration_approved',
    },
    'resource_type': {'Entreprise': 'Company', 'Utilisateur': 'User'},
    'result': {'succes': 'success', 'echec': 'failure'},
    'old_value': {'actif': 'active', 'inactif': 'inactive'},
    'new_value': {'actif': 'active', 'inactif': 'inactive'},
}


def _traduire_journal(sens: int) -> None:
    for colonne, correspondances in VALEURS_JOURNAL.items():
        for francais, anglais in correspondances.items():
            depuis, vers = (francais, anglais) if sens > 0 else (anglais, francais)
            op.execute(
                sa.text(f'UPDATE audit_log SET {colonne} = :vers WHERE {colonne} = :depuis')
                .bindparams(depuis=depuis, vers=vers)
            )


def upgrade() -> None:
    """Upgrade schema."""
    for table, _colonne, _cible, ancien, _nouveau, _regle in CLES_SANS_REGLE:
        ancienne_table = next(t[0] for t in TABLES if t[1] == table)
        op.drop_constraint(ancien, ancienne_table, type_='foreignkey')
    for ancienne, nouvelle, colonnes in TABLES:
        op.rename_table(ancienne, nouvelle)
        for ancienne_colonne, nouvelle_colonne in colonnes:
            op.alter_column(nouvelle, ancienne_colonne, new_column_name=nouvelle_colonne)
    for table, ancien, nouveau in CONTRAINTES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {ancien} TO {nouveau}')
    for ancien, nouveau in INDEX:
        op.execute(f'ALTER INDEX {ancien} RENAME TO {nouveau}')
    for table, colonne, cible, _ancien, nouveau, regle in CLES_SANS_REGLE:
        op.create_foreign_key(nouveau, table, cible, [colonne], ['id'], ondelete=regle)
    for nom, table, colonne in NOUVEAUX_INDEX:
        op.create_index(nom, table, [colonne])
    _traduire_journal(+1)


def downgrade() -> None:
    """Downgrade schema — noms, valeurs du journal et clés sans règle d'origine restaurés."""
    _traduire_journal(-1)
    for nom, table, _colonne in NOUVEAUX_INDEX:
        op.drop_index(nom, table_name=table)
    for table, _colonne, _cible, _ancien, nouveau, _regle in CLES_SANS_REGLE:
        op.drop_constraint(nouveau, table, type_='foreignkey')
    for ancien, nouveau in INDEX:
        op.execute(f'ALTER INDEX {nouveau} RENAME TO {ancien}')
    for table, ancien, nouveau in CONTRAINTES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {nouveau} TO {ancien}')
    for ancienne, nouvelle, colonnes in TABLES:
        for ancienne_colonne, nouvelle_colonne in colonnes:
            op.alter_column(nouvelle, nouvelle_colonne, new_column_name=ancienne_colonne)
        op.rename_table(nouvelle, ancienne)
    anciennes = {t[1]: t for t in TABLES}
    for table, colonne, cible, ancien, _nouveau, _regle in CLES_SANS_REGLE:
        ancienne_table, _, colonnes = anciennes[table]
        ancienne_colonne = {n: a for a, n in colonnes}[colonne]
        op.create_foreign_key(ancien, ancienne_table, anciennes[cible][0], [ancienne_colonne], ['id'])
