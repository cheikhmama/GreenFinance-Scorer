"""task 3.1: scoring_configs / scores — stored YAML content + hash, coverage_rate

Migration consolidée de la tâche 3.1 (docs/TASKS.md, glossaire docs/RENAME_PLAN.md §3d) :

1. configuration_ponderation -> scoring_configs, score_esg -> scores : colonnes, contraintes et
   index renommés.
2. scoring_configs : la méthodologie est stockée (content_yaml + content_hash, SHA-256 de sa forme
   canonique) au lieu d'un chemin de fichier (fichier_yaml, supprimé). L'unicité par version de la
   référence devient une unicité par empreinte et par propriétaire.
   Reprise de l'existant : une ligne reçoit le contenu du fichier qu'elle désigne seulement si ce
   fichier déclare encore la même version — sinon son contenu d'origine est inconnu et reste nul
   (CHECK : contenu et empreinte ensemble), jamais deviné.
3. scores : coverage_rate (0-1, nul pour les scores existants : non mesuré à l'époque) ;
   config_id -> scoring_configs en ON DELETE RESTRICT explicite + index.
4. analyse_entreprise.score_esg_id -> scores en ON DELETE SET NULL explicite + index (aucune règle
   jusqu'ici : supprimer un rapport scoré échouait dès qu'une analyse l'avait figé).
5. esg_reports.config_hash renseigné pour les rapports dont le score officiel a une configuration
   au contenu connu.

Revision ID: c1d4a8e2f935
Revises: c3a9f2d71b58
Create Date: 2026-10-03 09:00:00.000000

"""
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
import yaml

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c1d4a8e2f935'
down_revision: str | Sequence[str] | None = 'c3a9f2d71b58'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RACINE = Path(__file__).resolve().parents[2]
_CHEMIN_REFERENCE = 'config/weights/default.yaml'

TABLES = [('configuration_ponderation', 'scoring_configs'), ('score_esg', 'scores')]
COLONNES = {
    'scoring_configs': [
        ('nom', 'name'),
        ('date_creation', 'created_at'),
        ('utilisateur_id', 'owner_user_id'),
    ],
    'scores': [
        ('rapport_id', 'report_id'),
        ('configuration_id', 'config_id'),
        ('valeur_globale', 'global_score'),
        ('score_environnement', 'environmental_score'),
        ('score_social', 'social_score'),
        ('score_gouvernance', 'governance_score'),
        ('date_calcul', 'computed_at'),
    ],
}
CONTRAINTES_RENOMMEES = [
    ('scoring_configs', 'configuration_ponderation_pkey', 'scoring_configs_pkey'),
    ('scoring_configs', 'configuration_ponderation_utilisateur_id_fkey',
     'scoring_configs_owner_user_id_fkey'),
    ('scores', 'score_esg_pkey', 'scores_pkey'),
    ('scores', 'score_esg_rapport_id_fkey', 'scores_report_id_fkey'),
    ('scores', 'uq_score_esg_rapport_configuration', 'uq_scores_report_config'),
    ('scores', 'ck_score_esg_valeur_globale_bornee', 'ck_scores_global_score_range'),
    ('scores', 'ck_score_esg_environnement_borne', 'ck_scores_environmental_score_range'),
    ('scores', 'ck_score_esg_social_borne', 'ck_scores_social_score_range'),
    ('scores', 'ck_score_esg_gouvernance_borne', 'ck_scores_governance_score_range'),
]
INDEX_RENOMMES = [
    ('ix_configuration_ponderation_utilisateur_id', 'ix_scoring_configs_owner_user_id'),
]


def _empreinte(contenu_yaml: str) -> str:
    """Copie figée de app/scoring/config_schema.py::empreinte_configuration — une migration ne
    doit pas changer de comportement si le code applicatif évolue."""
    canonique = json.dumps(
        yaml.safe_load(contenu_yaml), sort_keys=True, separators=(',', ':'), ensure_ascii=False
    )
    return hashlib.sha256(canonique.encode('utf-8')).hexdigest()


def _contenu_si_meme_version(chemin: str, version: int) -> str | None:
    fichier = _RACINE / chemin
    if not fichier.is_file():
        return None
    contenu = fichier.read_text(encoding='utf-8')
    try:
        donnees = yaml.safe_load(contenu)
    except yaml.YAMLError:
        return None
    if not isinstance(donnees, dict) or donnees.get('version') != version:
        return None
    return contenu


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('score_esg_configuration_id_fkey', 'score_esg', type_='foreignkey')
    op.drop_constraint(
        'fk_analyse_entreprise_score_esg_id_score_esg', 'analyse_entreprise', type_='foreignkey'
    )
    op.drop_index(
        'uq_configuration_ponderation_reference_version', table_name='configuration_ponderation'
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

    # --- scoring_configs : contenu stocké --------------------------------------------------------
    op.add_column('scoring_configs', sa.Column('content_yaml', sa.Text(), nullable=True))
    op.add_column('scoring_configs', sa.Column('content_hash', sa.String(length=64), nullable=True))
    connexion = op.get_bind()
    deja_vues: set[tuple[str | None, str]] = set()
    for id_, fichier, version, proprietaire in connexion.execute(
        sa.text(
            'SELECT id, fichier_yaml, version, owner_user_id FROM scoring_configs '
            'ORDER BY created_at DESC'
        )
    ).all():
        contenu = _contenu_si_meme_version(fichier, version)
        if contenu is None:
            continue
        empreinte = _empreinte(contenu)
        cle = (str(proprietaire) if proprietaire else None, empreinte)
        if cle in deja_vues:
            continue  # la plus récente garde le contenu, les autres restent « inconnues »
        deja_vues.add(cle)
        connexion.execute(
            sa.text('UPDATE scoring_configs SET content_yaml = :c, content_hash = :h WHERE id = :id'),
            {'c': contenu, 'h': empreinte, 'id': id_},
        )
    op.drop_column('scoring_configs', 'fichier_yaml')
    op.create_check_constraint(
        'ck_scoring_configs_content_with_hash',
        'scoring_configs',
        '(content_yaml IS NULL) = (content_hash IS NULL)',
    )
    op.create_index(
        'uq_scoring_configs_reference_content_hash', 'scoring_configs', ['content_hash'],
        unique=True, postgresql_where=sa.text('owner_user_id IS NULL'),
    )
    op.create_index(
        'uq_scoring_configs_owner_content_hash', 'scoring_configs',
        ['owner_user_id', 'content_hash'],
        unique=True, postgresql_where=sa.text('owner_user_id IS NOT NULL'),
    )

    # --- scores -----------------------------------------------------------------------------
    op.add_column('scores', sa.Column('coverage_rate', sa.Float(), nullable=True))
    op.create_check_constraint(
        'ck_scores_coverage_rate_range', 'scores', 'coverage_rate BETWEEN 0 AND 1'
    )
    op.create_foreign_key(
        'scores_config_id_fkey', 'scores', 'scoring_configs', ['config_id'], ['id'],
        ondelete='RESTRICT',
    )
    op.create_index('ix_scores_config_id', 'scores', ['config_id'])

    # --- analyse_entreprise -------------------------------------------------------------------
    op.create_foreign_key(
        'fk_analyse_entreprise_score_esg_id_scores', 'analyse_entreprise', 'scores',
        ['score_esg_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index(
        'ix_analyse_entreprise_score_esg_id', 'analyse_entreprise', ['score_esg_id']
    )

    # --- esg_reports.config_hash : empreinte de la configuration du score officiel -------------
    op.execute(
        """
        UPDATE esg_reports r SET config_hash = officiel.content_hash
        FROM (
            SELECT DISTINCT ON (s.report_id) s.report_id, c.content_hash
            FROM scores s JOIN scoring_configs c ON c.id = s.config_id
            WHERE c.owner_user_id IS NULL
            ORDER BY s.report_id, s.computed_at DESC
        ) officiel
        WHERE r.id = officiel.report_id AND officiel.content_hash IS NOT NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema.

    Pertes assumées : le contenu stocké des configurations (l'ancien schéma ne gardait qu'un chemin,
    remis à config/weights/default.yaml), la couverture des scores, et esg_reports.config_hash /
    coverage_rate (jamais renseignés avant la tâche 3.1). Refuse de s'exécuter si deux
    configurations de référence partagent une version (contenus différents sous un même numéro,
    possible depuis la tâche 3.1) : l'ancien index d'unicité par version ne pourrait pas être
    recréé — à dédoublonner à la main."""
    connexion = op.get_bind()
    doublons = connexion.execute(
        sa.text(
            'SELECT version FROM scoring_configs WHERE owner_user_id IS NULL '
            'GROUP BY version HAVING count(*) > 1'
        )
    ).scalars().all()
    if doublons:
        raise RuntimeError(
            'Downgrade impossible : plusieurs configurations de référence par version '
            f'({sorted(doublons)}).'
        )

    op.execute('UPDATE esg_reports SET config_hash = NULL, coverage_rate = NULL')

    op.drop_index('ix_analyse_entreprise_score_esg_id', table_name='analyse_entreprise')
    op.drop_constraint(
        'fk_analyse_entreprise_score_esg_id_scores', 'analyse_entreprise', type_='foreignkey'
    )
    op.drop_index('ix_scores_config_id', table_name='scores')
    op.drop_constraint('scores_config_id_fkey', 'scores', type_='foreignkey')
    op.drop_constraint('ck_scores_coverage_rate_range', 'scores', type_='check')
    op.drop_column('scores', 'coverage_rate')

    op.drop_index('uq_scoring_configs_owner_content_hash', table_name='scoring_configs')
    op.drop_index('uq_scoring_configs_reference_content_hash', table_name='scoring_configs')
    op.drop_constraint('ck_scoring_configs_content_with_hash', 'scoring_configs', type_='check')
    op.add_column('scoring_configs', sa.Column(
        'fichier_yaml', sa.String(), nullable=False, server_default=_CHEMIN_REFERENCE
    ))
    op.alter_column('scoring_configs', 'fichier_yaml', server_default=None)
    op.drop_column('scoring_configs', 'content_hash')
    op.drop_column('scoring_configs', 'content_yaml')

    for ancien, nouveau in INDEX_RENOMMES:
        op.execute(f'ALTER INDEX {nouveau} RENAME TO {ancien}')
    for table, ancien, nouveau in CONTRAINTES_RENOMMEES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {nouveau} TO {ancien}')
    for table, colonnes in COLONNES.items():
        for ancien, nouveau in colonnes:
            op.alter_column(table, nouveau, new_column_name=ancien)
    for ancien, nouveau in TABLES:
        op.rename_table(nouveau, ancien)

    op.create_index(
        'uq_configuration_ponderation_reference_version', 'configuration_ponderation', ['version'],
        unique=True, postgresql_where=sa.text('utilisateur_id IS NULL'),
    )
    op.create_foreign_key(
        'score_esg_configuration_id_fkey', 'score_esg', 'configuration_ponderation',
        ['configuration_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_analyse_entreprise_score_esg_id_score_esg', 'analyse_entreprise', 'score_esg',
        ['score_esg_id'], ['id'],
    )
