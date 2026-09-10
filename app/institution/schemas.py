"""Schémas Pydantic d'entrée/sortie du module Institution.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2). RattachementPublic est
défini ici (l'Institution est l'initiatrice de l'invitation) et réutilisé par
app/researcher/schemas.py pour la même relation vue côté Chercheur.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import StatutAnalyse, StatutProjet, StatutRattachement


class ChercheurDisponible(BaseModel):
    """Compte CHERCHEUR actif, sélectionnable pour une invitation — même règle "sélection parmi
    les acteurs existants" que partout ailleurs (jamais de saisie libre d'identité)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nom: str | None


class InviterChercheurRequest(BaseModel):
    chercheur_id: uuid.UUID


class RattachementPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chercheur_id: uuid.UUID
    institution_id: uuid.UUID
    statut: StatutRattachement
    date_invitation: datetime
    date_reponse: datetime | None


class CreerProjetRequest(BaseModel):
    nom: str
    description: str | None = None


class AffecterChercheurRequest(BaseModel):
    chercheur_id: uuid.UUID


class DecisionAnalyseRequest(BaseModel):
    commentaire: str | None = None


class ProjetPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    nom: str
    description: str | None
    statut: StatutProjet
    date_creation: datetime
    date_cloture: datetime | None


class AffectationPublic(BaseModel):
    id: uuid.UUID
    chercheur_id: uuid.UUID
    chercheur_email: str
    date_affectation: datetime


class AnalyseResume(BaseModel):
    id: uuid.UUID
    chercheur_id: uuid.UUID
    titre: str
    statut: StatutAnalyse
    version: int
    date_creation: datetime
    date_soumission: datetime | None


class ProjetDetail(ProjetPublic):
    affectations: list[AffectationPublic]
    analyses: list[AnalyseResume]
