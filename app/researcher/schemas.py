"""Schémas Pydantic d'entrée/sortie du module Chercheur.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import StatutAnalyse, StatutProjet


class CreerAnalyseRequest(BaseModel):
    titre: str
    contenu: str
    entreprise_ids: list[uuid.UUID]


class ModifierAnalyseRequest(BaseModel):
    titre: str
    contenu: str
    entreprise_ids: list[uuid.UUID]


class AnalysePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    projet_id: uuid.UUID
    chercheur_id: uuid.UUID
    titre: str
    contenu: str
    statut: StatutAnalyse
    version: int
    analyse_precedente_id: uuid.UUID | None
    commentaire_institution: str | None
    date_creation: datetime
    date_soumission: datetime | None
    date_decision: datetime | None


class AnalyseDetail(AnalysePublic):
    entreprise_ids: list[uuid.UUID]


class ProjetAffecte(BaseModel):
    id: uuid.UUID
    nom: str
    description: str | None
    objectif: str | None
    date_debut: datetime | None
    date_fin_prevue: datetime | None
    date_limite: datetime | None
    statut: StatutProjet
    institution_email: str
