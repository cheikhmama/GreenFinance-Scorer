"""Entités de persistance de l'espace Auditeur.

AuditOpinion (table `audit_opinions`, tâche 4.7) porte la décision de l'auditeur sur un ESGReport — jamais une
saisie de valeur extraite (voir app/ingestion/models.py). La logique des
routes, de l'affectation et de la synthèse des avis reste implémentée à
l'Étape 11 (Espace Auditeur).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import AuditDecision, sa_enum_column

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
