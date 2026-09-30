"""Entités de persistance transverses, non rattachées à un module métier précis."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow

if TYPE_CHECKING:
    from app.auth.models import User


class AuditLogEntry(SQLModel, table=True):
    """Trace immuable des actions sensibles (Phase 3 §3.5) — jamais modifiée ni supprimée après
    création, sur le même principe que ESGReport et ce qui en dérive (voir
    app/ingestion/models.py). Écrite par app/core/audit.py::auditer, jamais construite ailleurs.

    Portée de cette passe : événements de compte et de session (connexion, déconnexion,
    changement de mot de passe, changement de rôle, désactivation) — pas encore les actions
    métier (affectation, décision, avis), déjà couvertes par structlog et Notification, et
    volontairement laissées hors de cette table pour ne pas dupliquer ce qui existe déjà.

    ip est nullable et jamais renseigné dans cette passe : sa capture dépend d'une politique de
    conservation/anonymisation non encore tranchée (même statut que les questions de rétention
    actées en Phase 0) — colonne posée à l'avance plutôt qu'ajoutée après coup.
    """

    __tablename__ = "audit_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    actor_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL", index=True
    )
    # Valeurs en anglais depuis la tâche 4.7 (ex. `login`, `User`, `success`) — libellés d'affichage
    # côté frontend.
    action: str
    resource_type: str
    resource_id: uuid.UUID | None = None
    occurred_at: datetime = Field(default_factory=utcnow)
    result: str
    old_value: str | None = None
    new_value: str | None = None
    correlation_id: str | None = None
    ip: str | None = None


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    message: str
    type: str
    # Cible de redirection au clic (ex. l'id d'un ESGReport) — jamais de FK stricte : le type de
    # ressource varie selon `type` (rapport, entreprise, ...) et certains types n'en ont pas
    # (ex. une invitation de rattachement, qui renvoie vers une liste, pas un id précis).
    resource_id: uuid.UUID | None = Field(default=None)
    sent_at: datetime = Field(default_factory=utcnow)
    read: bool = Field(default=False)

    user: "User" = Relationship(back_populates="notifications")
