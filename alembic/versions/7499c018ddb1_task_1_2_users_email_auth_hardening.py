"""task 1.2: users (English), lower-case e-mail, e-mail change requests

Migration consolidée de la tâche 1.2 (docs/TASKS.md, glossaire docs/RENAME_PLAN.md §3) :

1. utilisateur -> users, activation_compte -> account_activation_tokens,
   reinitialisation_mot_de_passe -> password_reset_tokens, avec leurs colonnes, contraintes et
   index renommés ; valeurs de Role en anglais (ADMIN, ENTERPRISE, AUDITOR, INVESTOR,
   RESEARCHER ; INSTITUTION inchangé — décision D1).
2. E-mail stocké en minuscules (ck_users_email_lowercase) : l'unicité existante sur `email`
   devient une unicité insensible à la casse. La migration refuse de s'appliquer s'il existe des
   comptes qui ne diffèrent que par la casse, plutôt que d'en fusionner ou supprimer un.
3. email_change_requests : changement d'e-mail confirmé par la nouvelle adresse.
4. Toute clé étrangère vers `users` reçoit une règle ON DELETE explicite et un index :
   - CASCADE pour les lignes qui n'existent que pour l'utilisateur (jetons, notifications, profil
     institution, rattachements chercheur/institution) ;
   - SET NULL pour une référence facultative sans valeur métier propre (acteur du journal) ;
   - RESTRICT pour les enregistrements de responsabilité ou métier (avis d'audit, analyses,
     affectations et projets, portefeuilles, configurations de pondération) : l'application ne
     supprime jamais un compte (elle le désactive), et une suppression administrative doit
     échouer plutôt qu'effacer une preuve. Une configuration de pondération en SET NULL
     deviendrait même la configuration de RÉFÉRENCE (utilisateur_id NULL). Ces règles seront
     revues avec la tâche de chaque module (docs/RENAME_PLAN.md §3.2).

Revision ID: 7499c018ddb1
Revises: 21e17187789f
Create Date: 2026-09-29 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7499c018ddb1'
down_revision: str | Sequence[str] | None = '21e17187789f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = [
    ('utilisateur', 'users'),
    ('activation_compte', 'account_activation_tokens'),
    ('reinitialisation_mot_de_passe', 'password_reset_tokens'),
]
_COLONNES_JETON = [
    ('utilisateur_id', 'user_id'),
    ('jeton_hache', 'token_hash'),
    ('date_creation', 'created_at'),
    ('date_expiration', 'expires_at'),
    ('utilise_le', 'used_at'),
]
COLONNES = {
    'users': [
        ('nom', 'name'),
        ('mot_de_passe_hache', 'password_hash'),
        ('date_creation', 'created_at'),
        ('actif', 'active'),
        ('date_activation', 'activated_at'),
    ],
    'account_activation_tokens': _COLONNES_JETON,
    'password_reset_tokens': _COLONNES_JETON,
}
CONTRAINTES_RENOMMEES = [
    ('users', 'utilisateur_pkey', 'users_pkey'),
    ('account_activation_tokens', 'activation_compte_pkey', 'account_activation_tokens_pkey'),
    ('password_reset_tokens', 'reinitialisation_mot_de_passe_pkey', 'password_reset_tokens_pkey'),
]
INDEX_RENOMMES = [
    ('ix_utilisateur_email', 'ix_users_email'),
    ('ix_activation_compte_jeton_hache', 'ix_account_activation_tokens_token_hash'),
    ('ix_activation_compte_utilisateur_id', 'ix_account_activation_tokens_user_id'),
    ('ix_reinitialisation_mot_de_passe_jeton_hache', 'ix_password_reset_tokens_token_hash'),
    ('ix_reinitialisation_mot_de_passe_utilisateur_id', 'ix_password_reset_tokens_user_id'),
]
ROLES = {
    'ADMINISTRATEUR': 'ADMIN',
    'ENTREPRISE': 'ENTERPRISE',
    'AUDITEUR': 'AUDITOR',
    'INVESTISSEUR': 'INVESTOR',
    'CHERCHEUR': 'RESEARCHER',
}

# (table, colonne (nom après migration), ancien nom de contrainte, nouveau nom, ON DELETE).
# companies.owner_user_id, esg_reports.auditor_id et esg_metrics.overridden_by_id ont déjà leur
# règle (SET NULL, tâche 1.1) : le renommage de la table référencée les suit sans changement.
CLES_ETRANGERES = [
    ('account_activation_tokens', 'user_id',
     'activation_compte_utilisateur_id_fkey', 'account_activation_tokens_user_id_fkey', 'CASCADE'),
    ('password_reset_tokens', 'user_id',
     'reinitialisation_mot_de_passe_utilisateur_id_fkey', 'password_reset_tokens_user_id_fkey',
     'CASCADE'),
    ('notification', 'utilisateur_id',
     'notification_utilisateur_id_fkey', 'notification_utilisateur_id_fkey', 'CASCADE'),
    ('institution_profil', 'utilisateur_id',
     'institution_profil_utilisateur_id_fkey', 'institution_profil_utilisateur_id_fkey', 'CASCADE'),
    ('chercheur_institution', 'chercheur_id',
     'chercheur_institution_chercheur_id_fkey', 'chercheur_institution_chercheur_id_fkey',
     'CASCADE'),
    ('chercheur_institution', 'institution_id',
     'chercheur_institution_institution_id_fkey', 'chercheur_institution_institution_id_fkey',
     'CASCADE'),
    ('journal_audit', 'acteur_id',
     'journal_audit_acteur_id_fkey', 'journal_audit_acteur_id_fkey', 'SET NULL'),
    ('avis_audit', 'auditeur_id',
     'avis_audit_auditeur_id_fkey', 'avis_audit_auditeur_id_fkey', 'RESTRICT'),
    ('analyse', 'chercheur_id',
     'analyse_chercheur_id_fkey', 'analyse_chercheur_id_fkey', 'RESTRICT'),
    ('affectation_projet', 'chercheur_id',
     'affectation_projet_chercheur_id_fkey', 'affectation_projet_chercheur_id_fkey', 'RESTRICT'),
    ('projet', 'institution_id',
     'projet_institution_id_fkey', 'projet_institution_id_fkey', 'RESTRICT'),
    ('portefeuille', 'investisseur_id',
     'portefeuille_investisseur_id_fkey', 'portefeuille_investisseur_id_fkey', 'RESTRICT'),
    ('configuration_ponderation', 'utilisateur_id',
     'configuration_ponderation_utilisateur_id_fkey',
     'configuration_ponderation_utilisateur_id_fkey', 'RESTRICT'),
]
# Colonnes référençantes sans index jusqu'ici (les autres en ont déjà un, simple ou composite
# commençant par la colonne).
INDEX_AJOUTES = [
    ('notification', 'utilisateur_id'),
    ('chercheur_institution', 'institution_id'),
    ('journal_audit', 'acteur_id'),
    ('avis_audit', 'auditeur_id'),
    ('analyse', 'chercheur_id'),
    ('affectation_projet', 'chercheur_id'),
    ('projet', 'institution_id'),
    ('portefeuille', 'investisseur_id'),
    ('configuration_ponderation', 'utilisateur_id'),
]


def _case(colonne: str, correspondances: dict[str, str]) -> str:
    branches = ' '.join(f"WHEN '{avant}' THEN '{apres}'" for avant, apres in correspondances.items())
    return f'CASE {colonne} {branches} ELSE {colonne} END'


def upgrade() -> None:
    """Upgrade schema."""
    connexion = op.get_bind()
    doublons = connexion.execute(sa.text(
        'SELECT lower(email), count(*) FROM utilisateur GROUP BY lower(email) HAVING count(*) > 1'
    )).fetchall()
    if doublons:
        raise RuntimeError(
            'Des comptes ne diffèrent que par la casse de leur e-mail : '
            f'{[e for e, _ in doublons]} — les fusionner ou en renommer un avant cette migration.'
        )

    tables_avant = {nouveau: ancien for ancien, nouveau in TABLES}
    for table, _colonne, ancien, _nouveau, _regle in CLES_ETRANGERES:
        op.drop_constraint(ancien, tables_avant.get(table, table), type_='foreignkey')

    for ancien, nouveau in TABLES:
        op.rename_table(ancien, nouveau)
    for table, colonnes in COLONNES.items():
        for ancien, nouveau in colonnes:
            op.alter_column(table, ancien, new_column_name=nouveau)
    for table, ancien, nouveau in CONTRAINTES_RENOMMEES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {ancien} TO {nouveau}')
    for ancien, nouveau in INDEX_RENOMMES:
        op.execute(f'ALTER INDEX {ancien} RENAME TO {nouveau}')

    op.execute('UPDATE users SET email = lower(email) WHERE email <> lower(email)')
    op.create_check_constraint('ck_users_email_lowercase', 'users', 'email = lower(email)')
    op.execute(f"UPDATE users SET role = {_case('role', ROLES)}")

    op.create_table(
        'email_change_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('new_email', sa.String(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], name='email_change_requests_user_id_fkey',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name='email_change_requests_pkey'),
    )
    op.create_index(
        'ix_email_change_requests_token_hash', 'email_change_requests', ['token_hash'], unique=True
    )
    op.create_index('ix_email_change_requests_user_id', 'email_change_requests', ['user_id'])

    for table, colonne, _ancien, nouveau, regle in CLES_ETRANGERES:
        op.create_foreign_key(nouveau, table, 'users', [colonne], ['id'], ondelete=regle)
    for table, colonne in INDEX_AJOUTES:
        op.create_index(f'ix_{table}_{colonne}', table, [colonne])


def downgrade() -> None:
    """Downgrade schema — rétablit noms, valeurs et contraintes d'avant la tâche 1.2.

    Pertes assumées : les demandes de changement d'e-mail en cours sont supprimées, et les e-mails
    restent en minuscules (la casse d'origine n'est pas conservée)."""
    for table, colonne in INDEX_AJOUTES:
        op.drop_index(f'ix_{table}_{colonne}', table_name=table)
    for table, _colonne, _ancien, nouveau, _regle in CLES_ETRANGERES:
        op.drop_constraint(nouveau, table, type_='foreignkey')

    op.drop_index('ix_email_change_requests_user_id', table_name='email_change_requests')
    op.drop_index('ix_email_change_requests_token_hash', table_name='email_change_requests')
    op.drop_table('email_change_requests')

    op.execute(f"UPDATE users SET role = {_case('role', {v: k for k, v in ROLES.items()})}")
    op.drop_constraint('ck_users_email_lowercase', 'users', type_='check')

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
    tables_avant = {nouveau: ancien for ancien, nouveau in TABLES}
    colonnes_avant = {
        (table, nouveau): ancien
        for table, colonnes in COLONNES.items() for ancien, nouveau in colonnes
    }
    for table, colonne, ancien, _nouveau, _regle in CLES_ETRANGERES:
        op.create_foreign_key(
            ancien,
            tables_avant.get(table, table),
            'utilisateur',
            [colonnes_avant.get((table, colonne), colonne)],
            ['id'],
        )
