"""task 1.6: one reference scoring configuration per version, official_score backfill

Migration de la tâche 1.6 (docs/TASKS.md, validation atomique) :

1. Fusionne les doublons de configuration de référence (utilisateur_id NULL) d'une même version.
   L'ancien obtenir_configuration_reference créait une ligne de plus à chaque fois que la version
   la plus récente en base différait de celle du fichier YAML (retour à une version antérieure,
   alternance de fichiers), et pouvait en créer deux sous deux validations concurrentes. Une même
   version désigne la même méthodologie : la ligne la plus ancienne est conservée, les scores des
   doublons y sont rattachés ; un score qui ferait doublon pour le même rapport sous cette version
   est supprimé (même méthodologie, même rapport : il n'apporte rien).
2. Index unique partiel uq_configuration_ponderation_reference_version (version WHERE
   utilisateur_id IS NULL) : cible de l'INSERT ... ON CONFLICT de
   app/scoring/engine.py::obtenir_configuration_reference, qui ne commite plus.
3. Renseigne esg_reports.official_score (colonne de la tâche 1.1) pour les rapports VALIDATED à
   partir de leur score sous la version de référence la plus récente.

Revision ID: 834bf70ae1b9
Revises: 7499c018ddb1
Create Date: 2026-09-29 22:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '834bf70ae1b9'
down_revision: str | Sequence[str] | None = '7499c018ddb1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TEMPORARY TABLE _references_classees ON COMMIT DROP AS
        SELECT id,
               version,
               row_number() OVER (PARTITION BY version ORDER BY date_creation, id) AS rang,
               first_value(id) OVER (PARTITION BY version ORDER BY date_creation, id) AS conservee
        FROM configuration_ponderation
        WHERE utilisateur_id IS NULL
    """)
    # Un rapport ne garde qu'un score par version de référence : le plus ancien (celui de la ligne
    # conservée ou du premier doublon).
    op.execute("""
        DELETE FROM score_esg s
        USING _references_classees r
        WHERE s.configuration_id = r.id
          AND EXISTS (
              SELECT 1
              FROM score_esg s2
              JOIN _references_classees r2 ON r2.id = s2.configuration_id
              WHERE s2.rapport_id = s.rapport_id
                AND r2.version = r.version
                AND r2.rang < r.rang
          )
    """)
    op.execute("""
        UPDATE score_esg s
        SET configuration_id = r.conservee
        FROM _references_classees r
        WHERE s.configuration_id = r.id AND r.rang > 1
    """)
    op.execute("""
        DELETE FROM configuration_ponderation c
        USING _references_classees r
        WHERE c.id = r.id AND r.rang > 1
    """)
    op.execute('DROP TABLE _references_classees')

    op.create_index(
        'uq_configuration_ponderation_reference_version',
        'configuration_ponderation',
        ['version'],
        unique=True,
        postgresql_where=sa.text('utilisateur_id IS NULL'),
    )

    op.execute("""
        UPDATE esg_reports r
        SET official_score = dernier.valeur_globale
        FROM (
            SELECT DISTINCT ON (s.rapport_id) s.rapport_id, s.valeur_globale
            FROM score_esg s
            JOIN configuration_ponderation c ON c.id = s.configuration_id
            WHERE c.utilisateur_id IS NULL
            ORDER BY s.rapport_id, c.version DESC
        ) AS dernier
        WHERE r.id = dernier.rapport_id AND r.status = 'VALIDATED'
    """)


def downgrade() -> None:
    """Downgrade schema.

    Pertes assumées : les doublons fusionnés ne sont pas recréés (ils ne portaient aucune
    information distincte), official_score est remis à NULL comme avant cette migration."""
    op.execute('UPDATE esg_reports SET official_score = NULL')
    op.drop_index(
        'uq_configuration_ponderation_reference_version', table_name='configuration_ponderation'
    )
