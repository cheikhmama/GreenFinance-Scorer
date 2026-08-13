"""Entités de persistance transverses, non rattachées à un module métier précis."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow

if TYPE_CHECKING:
    from app.auth.models import Utilisateur


class Notification(SQLModel, table=True):
    __tablename__ = "notification"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    utilisateur_id: uuid.UUID = Field(foreign_key="utilisateur.id")
    message: str
    type: str
    date_envoi: datetime = Field(default_factory=utcnow)
    lu: bool = Field(default=False)

    utilisateur: "Utilisateur" = Relationship(back_populates="notifications")
