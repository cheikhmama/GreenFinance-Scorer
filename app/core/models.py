"""Entités de persistance transverses, non rattachées à un module métier précis."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow

if TYPE_CHECKING:
    from app.auth.models import Utilisateur


class JournalAudit(SQLModel, table=True):
    """Trace immuable des actions sensibles (Phase 3 §3.5) — jamais modifiée ni supprimée après
    création, sur le même principe que RapportESG et ce qui en dérive (voir
    app/ingestion/models.py). Écrite par app/core/audit.py::auditer, jamais construite ailleurs.

    Portée de cette passe : événements de compte et de session (connexion, déconnexion,
    changement de mot de passe, changement de rôle, désactivation) — pas encore les actions
    métier (affectation, décision, avis), déjà couvertes par structlog et Notification, et
    volontairement laissées hors de cette table pour ne pas dupliquer ce qui existe déjà.

    ip est nullable et jamais renseigné dans cette passe : sa capture dépend d'une politique de
    conservation/anonymisation non encore tranchée (même statut que les questions de rétention
    actées en Phase 0) — colonne posée à l'avance plutôt qu'ajoutée après coup.
    """

    __tablename__ = "journal_audit"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    acteur_id: uuid.UUID | None = Field(default=None, foreign_key="utilisateur.id")
    action: str
    type_ressource: str
    id_ressource: uuid.UUID | None = None
    date: datetime = Field(default_factory=utcnow)
    resultat: str
    ancienne_valeur: str | None = None
    nouvelle_valeur: str | None = None
    correlation_id: str | None = None
    ip: str | None = None


class Notification(SQLModel, table=True):
    __tablename__ = "notification"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    utilisateur_id: uuid.UUID = Field(foreign_key="utilisateur.id")
    message: str
    type: str
    date_envoi: datetime = Field(default_factory=utcnow)
    lu: bool = Field(default=False)

    utilisateur: "Utilisateur" = Relationship(back_populates="notifications")
