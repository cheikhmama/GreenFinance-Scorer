"""Entités de persistance de l'espace Auditeur.

AuditOpinion (table `audit_opinions`, tâche 4.7) porte la décision de l'auditeur sur un ESGReport — jamais une
saisie de valeur extraite (voir app/ingestion/models.py). La logique des
routes, de l'affectation et de la synthèse des avis reste implémentée à
l'Étape 11 (Espace Auditeur).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import (
    AuditDecision,
    MetricReviewStatus,
    ReviewReason,
    sa_enum_column,
)

if TYPE_CHECKING:
    from app.auth.models import User
    from app.ingestion.models import ESGReport


class AuditOpinion(SQLModel, table=True):
    __tablename__ = "audit_opinions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    report_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE", index=True)
    # Champ interne réservé à l'accountability et au suivi de performance
    # des auditeurs (Espace Administrateur). Ne doit JAMAIS être exposé
    # par une route ou un schéma de réponse accessible à un compte
    # Entreprise — règle d'accès à faire respecter strictement à partir
    # de l'Étape 9.
    auditor_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    decision: AuditDecision = Field(sa_column=sa_enum_column(AuditDecision))
    # Porte notamment la confirmation ou l'infirmation des données
    # manquantes/anomalies déjà détectées par le pipeline automatique.
    comment: str | None = None
    submitted_at: datetime = Field(default_factory=utcnow)

    report: "ESGReport" = Relationship(back_populates="audit_opinions")
    auditor: "User" = Relationship(back_populates="audit_opinions")


class MetricReview(SQLModel, table=True):
    """Journal append-only des revues de l'Auditeur sur les valeurs extraites (tâche 5.6) : une
    ligne par décision — accepter, corriger, déclarer non trouvée —, jamais modifiée ni effacée
    (un déclencheur PostgreSQL refuse UPDATE, DELETE et TRUNCATE, voir la migration). La dernière
    entrée d'une valeur fait foi ; ESGMetric / CarbonEmission en portent l'état courant.

    Toutes les clés sont RESTRICT : une valeur revue, son rapport et son auditeur ne disparaissent
    pas sous leur trace."""

    __tablename__ = "metric_reviews"
    __table_args__ = (
        CheckConstraint(
            "(metric_id IS NULL) <> (emission_id IS NULL)",
            name="ck_metric_reviews_one_target",
        ),
        CheckConstraint(
            "(decision = 'OVERRIDDEN') = (new_value IS NOT NULL)",
            name="ck_metric_reviews_new_value_iff_overridden",
        ),
        CheckConstraint(
            "decision = 'ACCEPTED' OR reason IS NOT NULL",
            name="ck_metric_reviews_reason_unless_accepted",
        ),
        CheckConstraint(
            "decision <> 'PENDING'",
            name="ck_metric_reviews_decision_not_pending",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    report_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="RESTRICT", index=True)
    metric_id: uuid.UUID | None = Field(
        default=None, foreign_key="esg_metrics.id", ondelete="RESTRICT", index=True
    )
    emission_id: uuid.UUID | None = Field(
        default=None, foreign_key="carbon_emissions.id", ondelete="RESTRICT", index=True
    )
    decision: MetricReviewStatus = Field(sa_column=sa_enum_column(MetricReviewStatus))
    # Valeur extraite au moment de la revue, et valeur corrigée (OVERRIDDEN seulement).
    original_value: float
    new_value: float | None = None
    reason: ReviewReason | None = Field(
        default=None, sa_column=sa_enum_column(ReviewReason, nullable=True)
    )
    comment: str | None = Field(default=None, max_length=2000)
    auditor_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    created_at: datetime = Field(default_factory=utcnow)
