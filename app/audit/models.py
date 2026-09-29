"""Entités de persistance de l'espace Auditeur.

AvisAudit porte la décision de l'auditeur sur un ESGReport — jamais une
saisie de valeur extraite (voir app/ingestion/models.py). La logique des
routes, de l'affectation et de la synthèse des avis reste implémentée à
l'Étape 11 (Espace Auditeur).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import DecisionAudit, sa_enum_column

if TYPE_CHECKING:
    from app.auth.models import User
    from app.ingestion.models import ESGReport


class AvisAudit(SQLModel, table=True):
    __tablename__ = "avis_audit"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rapport_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE", index=True)
    # Champ interne réservé à l'accountability et au suivi de performance
    # des auditeurs (Espace Administrateur). Ne doit JAMAIS être exposé
    # par une route ou un schéma de réponse accessible à un compte
    # Entreprise — règle d'accès à faire respecter strictement à partir
    # de l'Étape 9.
    auditeur_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    decision: DecisionAudit = Field(sa_column=sa_enum_column(DecisionAudit))
    # Porte notamment la confirmation ou l'infirmation des données
    # manquantes/anomalies déjà détectées par le pipeline automatique.
    commentaire: str | None = None
    date_avis: datetime = Field(default_factory=utcnow)

    rapport: "ESGReport" = Relationship(back_populates="audit_opinions")
    auditeur: "User" = Relationship(back_populates="audit_opinions")
