"""Entités de persistance du scoring ESG (configuration de pondération, score calculé).

ConfigurationPonderation.utilisateur_id est nul pour la configuration de
référence maintenue par l'Administrateur, et renseigné pour toute
configuration personnalisée — quel que soit le rôle de son créateur parmi
Investisseur, Chercheur et Institution (pas réservé à l'Investisseur). Le
moteur de calcul reste implémenté à l'Étape 12 (Scoring ESG).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow

if TYPE_CHECKING:
    from app.auth.models import Utilisateur
    from app.ingestion.models import RapportESG


class ConfigurationPonderation(SQLModel, table=True):
    __tablename__ = "configuration_ponderation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    nom: str
    version: int
    fichier_yaml: str
    date_creation: datetime = Field(default_factory=utcnow)
    # Nul = configuration de référence (Administrateur). Renseigné =
    # personnalisation par un Investisseur, Chercheur ou Institution — la
    # contrainte "une seule référence à la fois" est applicative, pas
    # imposée en base à ce stade (voir tests/integration/test_models_scoring.py).
    utilisateur_id: uuid.UUID | None = Field(default=None, foreign_key="utilisateur.id")

    utilisateur: Optional["Utilisateur"] = Relationship(
        back_populates="configurations_ponderation"
    )
    scores: list["ScoreESG"] = Relationship(back_populates="configuration")


class ScoreESG(SQLModel, table=True):
    __tablename__ = "score_esg"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rapport_id: uuid.UUID = Field(foreign_key="rapport_esg.id")
    configuration_id: uuid.UUID = Field(foreign_key="configuration_ponderation.id")
    valeur_globale: float
    score_environnement: float
    score_social: float
    score_gouvernance: float
    date_calcul: datetime = Field(default_factory=utcnow)

    rapport: "RapportESG" = Relationship(back_populates="scores")
    configuration: ConfigurationPonderation = Relationship(back_populates="scores")
