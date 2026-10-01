"""task 5.6: metric review (append-only log) and the four audit opinion values

- `metric_reviews`: one row per auditor decision on an extracted value (metric or carbon row).
  A trigger refuses UPDATE, DELETE and TRUNCATE: the log is append-only. All its foreign keys are
  RESTRICT.
- `esg_metrics` / `carbon_emissions`: current state `review_status` (default `PENDING`) and
  `audited_value`. The former override columns of `esg_metrics` (never written by the
  application) are dropped; any override they held becomes `OVERRIDDEN` + its log entry.
- `audit_opinions.decision`: RECOMMANDE_VALIDATION → FAVORABLE, DEMANDE_CLARIFICATION →
  CORRECTION_REQUIRED, RECOMMANDE_REJET → UNFAVORABLE.

Downgrade: FAVORABLE_WITH_RESERVATIONS has no former equivalent and goes back to
RECOMMANDE_VALIDATION (its comment keeps the reservations); the latest override of each metric
returns to the former columns; ACCEPTED / NOT_FOUND decisions and the log itself are lost.

Revision ID: e3b8c5d1f9a2
Revises: d9f4b7e1a5c8
Create Date: 2026-10-02 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e3b8c5d1f9a2'
down_revision: str | Sequence[str] | None = 'd9f4b7e1a5c8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES_EXTRAITES = ('esg_metrics', 'carbon_emissions')
DECISIONS = {
    'RECOMMANDE_VALIDATION': 'FAVORABLE',
    'DEMANDE_CLARIFICATION': 'CORRECTION_REQUIRED',
    'RECOMMANDE_REJET': 'UNFAVORABLE',
}


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'metric_reviews',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('report_id', sa.Uuid(), nullable=False),
        sa.Column('metric_id', sa.Uuid(), nullable=True),
        sa.Column('emission_id', sa.Uuid(), nullable=True),
        sa.Column('decision', sa.String(length=64), nullable=False),
        sa.Column('original_value', sa.Float(), nullable=False),
        sa.Column('new_value', sa.Float(), nullable=True),
        sa.Column('reason', sa.String(length=64), nullable=True),
        sa.Column('comment', sa.String(length=2000), nullable=True),
        sa.Column('auditor_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['esg_reports.id'], name='metric_reviews_report_id_fkey', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['metric_id'], ['esg_metrics.id'], name='metric_reviews_metric_id_fkey', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['emission_id'], ['carbon_emissions.id'], name='metric_reviews_emission_id_fkey', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['auditor_id'], ['users.id'], name='metric_reviews_auditor_id_fkey', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='metric_reviews_pkey'),
        sa.CheckConstraint('(metric_id IS NULL) <> (emission_id IS NULL)', name='ck_metric_reviews_one_target'),
        sa.CheckConstraint("(decision = 'OVERRIDDEN') = (new_value IS NOT NULL)", name='ck_metric_reviews_new_value_iff_overridden'),
        sa.CheckConstraint("decision = 'ACCEPTED' OR reason IS NOT NULL", name='ck_metric_reviews_reason_unless_accepted'),
        sa.CheckConstraint("decision <> 'PENDING'", name='ck_metric_reviews_decision_not_pending'),
    )
    for colonne in ('report_id', 'metric_id', 'emission_id', 'auditor_id'):
        op.create_index(f'ix_metric_reviews_{colonne}', 'metric_reviews', [colonne])
    op.execute(
        """
        CREATE FUNCTION metric_reviews_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'metric_reviews est un journal append-only : % refusé', TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER metric_reviews_no_update_delete BEFORE UPDATE OR DELETE ON metric_reviews "
        "FOR EACH ROW EXECUTE FUNCTION metric_reviews_append_only()"
    )
    op.execute(
        "CREATE TRIGGER metric_reviews_no_truncate BEFORE TRUNCATE ON metric_reviews "
        "FOR EACH STATEMENT EXECUTE FUNCTION metric_reviews_append_only()"
    )

    for table in TABLES_EXTRAITES:
        op.add_column(table, sa.Column('review_status', sa.String(length=64), nullable=False, server_default='PENDING'))
        op.add_column(table, sa.Column('audited_value', sa.Float(), nullable=True))

    # Anciennes corrections (colonnes jamais écrites par l'application, reprises par sûreté).
    op.execute(
        """
        INSERT INTO metric_reviews (id, report_id, metric_id, decision, original_value, new_value,
                                    reason, comment, auditor_id, created_at)
        SELECT gen_random_uuid(), m.report_id, m.id, 'OVERRIDDEN', m.value, m.override_value,
               'OTHER', m.override_reason, m.overridden_by_id, COALESCE(m.overridden_at, now())
        FROM esg_metrics m
        WHERE m.auditor_overridden AND m.override_value IS NOT NULL AND m.overridden_by_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE esg_metrics SET review_status = 'OVERRIDDEN', audited_value = override_value
        WHERE auditor_overridden AND override_value IS NOT NULL
        """
    )
    op.drop_constraint('esg_metrics_overridden_by_id_fkey', 'esg_metrics', type_='foreignkey')
    op.drop_index('ix_esg_metrics_overridden_by_id', table_name='esg_metrics')
    for colonne in ('auditor_overridden', 'override_value', 'override_reason', 'overridden_by_id', 'overridden_at'):
        op.drop_column('esg_metrics', colonne)

    for ancienne, nouvelle in DECISIONS.items():
        op.execute(
            sa.text("UPDATE audit_opinions SET decision = :n WHERE decision = :a").bindparams(a=ancienne, n=nouvelle)
        )


def downgrade() -> None:
    """Downgrade schema."""
    for ancienne, nouvelle in DECISIONS.items():
        op.execute(
            sa.text("UPDATE audit_opinions SET decision = :a WHERE decision = :n").bindparams(a=ancienne, n=nouvelle)
        )
    op.execute("UPDATE audit_opinions SET decision = 'RECOMMANDE_VALIDATION' WHERE decision = 'FAVORABLE_WITH_RESERVATIONS'")

    op.add_column('esg_metrics', sa.Column('auditor_overridden', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('esg_metrics', sa.Column('override_value', sa.Float(), nullable=True))
    op.add_column('esg_metrics', sa.Column('override_reason', sa.String(), nullable=True))
    op.add_column('esg_metrics', sa.Column('overridden_by_id', sa.Uuid(), nullable=True))
    op.add_column('esg_metrics', sa.Column('overridden_at', sa.DateTime(), nullable=True))
    op.alter_column('esg_metrics', 'auditor_overridden', server_default=None)
    op.create_index('ix_esg_metrics_overridden_by_id', 'esg_metrics', ['overridden_by_id'])
    op.create_foreign_key(
        'esg_metrics_overridden_by_id_fkey', 'esg_metrics', 'users',
        ['overridden_by_id'], ['id'], ondelete='SET NULL',
    )
    op.execute(
        """
        WITH derniere AS (
            SELECT DISTINCT ON (metric_id) metric_id, comment, auditor_id, created_at
            FROM metric_reviews
            WHERE metric_id IS NOT NULL AND decision = 'OVERRIDDEN'
            ORDER BY metric_id, created_at DESC
        )
        UPDATE esg_metrics m
        SET auditor_overridden = true, override_value = m.audited_value, override_reason = d.comment,
            overridden_by_id = d.auditor_id, overridden_at = d.created_at
        FROM derniere d
        WHERE m.id = d.metric_id AND m.review_status = 'OVERRIDDEN'
        """
    )
    for table in TABLES_EXTRAITES:
        op.drop_column(table, 'audited_value')
        op.drop_column(table, 'review_status')

    op.execute("DROP TABLE metric_reviews")
    op.execute("DROP FUNCTION metric_reviews_append_only()")
