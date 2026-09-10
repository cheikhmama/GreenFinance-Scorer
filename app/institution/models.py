"""Entités de persistance de l'espace Institution : projets et affectations (Étape 17).

Un Projet est créé par une Institution et peut affecter plusieurs Chercheurs (chacun avec son
propre fil d'analyse, voir app/researcher/models.py::Analyse) — jamais l'inverse, un Chercheur ne
crée jamais de projet. L'affectation exige un rattachement ChercheurInstitution déjà ACCEPTE
(vérifié par app/institution/projets.py, pas ici : ce module ne pose que le schéma).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import StatutProjet, sa_enum_column

if TYPE_CHECKING:
    from app.auth.models import Utilisateur
    from app.researcher.models import Analyse


class Projet(SQLModel, table=True):
    __tablename__ = "projet"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    institution_id: uuid.UUID = Field(foreign_key="utilisateur.id")
    nom: str
    description: str | None = None
    statut: StatutProjet = Field(default=StatutProjet.OUVERT, sa_column=sa_enum_column(StatutProjet))
    date_creation: datetime = Field(default_factory=utcnow)
    # Nulle tant que le projet est OUVERT — renseignée une seule fois à la clôture, jamais
    # recalculée (même principe que Entreprise.date_publication).
    date_cloture: datetime | None = None

    institution: "Utilisateur" = Relationship(back_populates="projets")
    affectations: list["AffectationProjet"] = Relationship(back_populates="projet")
    analyses: list["Analyse"] = Relationship(back_populates="projet")


class AffectationProjet(SQLModel, table=True):
    __tablename__ = "affectation_projet"
    __table_args__ = (
        UniqueConstraint("projet_id", "chercheur_id", name="uq_affectation_projet_chercheur"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    projet_id: uuid.UUID = Field(foreign_key="projet.id")
    chercheur_id: uuid.UUID = Field(foreign_key="utilisateur.id")
    date_affectation: datetime = Field(default_factory=utcnow)

    projet: Projet = Relationship(back_populates="affectations")
    chercheur: "Utilisateur" = Relationship(back_populates="affectations_projet")
