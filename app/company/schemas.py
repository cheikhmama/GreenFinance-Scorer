"""Schémas Pydantic d'entrée/sortie du module Entreprise.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EntreprisePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom: str
    secteur: str
    pays: str
    logo: str | None
    description: str | None
    site_officiel: str | None
    actif: bool
    montant_minimum_investissement: float | None
    date_publication: datetime | None
