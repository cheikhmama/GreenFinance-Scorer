"""Schémas Pydantic d'entrée/sortie du module Entreprise.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import DevisePosition, TypeRapport


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
    devise_montant_minimum: DevisePosition | None
    date_publication: datetime | None


class ImporterRapportParURLRequest(BaseModel):
    """Corps de POST /company/rapports/import-url (CanalDepot.AUTOMATIQUE). entreprise_id n'est
    lu que pour un appelant Administrateur -- un appelant Entreprise est toujours rattaché à sa
    propre entreprise (voir app/company/router.py), un entreprise_id fourni par lui est ignoré."""

    url: str
    type: TypeRapport
    annee_reporting: int
    entreprise_id: uuid.UUID | None = None
