"""Schémas Pydantic transverses, partagés par plusieurs modules métier.

Contrairement à un schemas.py de module (entrées/sorties propres à un domaine, voir
ARCHITECTURE.md §2), ce fichier porte les formes génériques réutilisables (pagination) et les
schémas des entités transverses de app/core/models.py (Notification, JournalAudit) qui
n'appartiennent à aucun espace acteur en particulier.
"""

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Enveloppe commune à toute liste paginée de l'API : {"items", "page", "page_size",
    "total", "pages"}.

    Utilisée depuis GET /admin/utilisateurs et GET /admin/entreprises/publiables (recherche +
    pagination par offset/limit dans l'espace Administrateur) — première liste à en avoir eu
    réellement besoin, posée à l'avance pour que toute liste paginée future parte sur cette
    forme au lieu d'en inventer une autre.
    """

    items: list[T]
    page: int
    page_size: int
    total: int
    pages: int


class NotificationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    message: str
    date_envoi: datetime
    lu: bool
