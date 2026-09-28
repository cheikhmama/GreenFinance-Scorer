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
    from app.company.models import Entreprise
    from app.ingestion.models import RapportESG
    from app.researcher.models import Analyse


class Projet(SQLModel, table=True):
    __tablename__ = "projet"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    institution_id: uuid.UUID = Field(foreign_key="utilisateur.id")
    nom: str
    description: str | None = None
    # Distinct de description (texte libre) : objectif porte la finalité de la mission, demandée
    # explicitement comme champ séparé (Étape 17bis).
    objectif: str | None = None
    # Période prévue du projet (date_debut -> date_fin_prevue) et échéance de remise du travail
    # (date_limite, optionnelle, distincte de la fin de période) — toutes trois de simples
    # intentions posées par l'Institution, jamais recalculées. date_cloture (ci-dessous) reste la
    # seule date à valeur réelle : la date effective de clôture.
    date_debut: datetime | None = None
    date_fin_prevue: datetime | None = None
    date_limite: datetime | None = None
    statut: StatutProjet = Field(default=StatutProjet.OUVERT, sa_column=sa_enum_column(StatutProjet))
    date_creation: datetime = Field(default_factory=utcnow)
    # Nulle tant que le projet est OUVERT — renseignée une seule fois à la clôture, jamais
    # recalculée (même principe que Entreprise.date_publication).
    date_cloture: datetime | None = None

    institution: "Utilisateur" = Relationship(back_populates="projets")
    affectations: list["AffectationProjet"] = Relationship(back_populates="projet")
    analyses: list["Analyse"] = Relationship(back_populates="projet")
    perimetre: list["ProjetEntreprise"] = Relationship(back_populates="projet")
    documents: list["ProjetDocument"] = Relationship(back_populates="projet")


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


class ProjetEntreprise(SQLModel, table=True):
    """Le périmètre d'un projet : les entreprises que l'Institution autorise à comparer dans ce
    projet précis (Étape 17bis). Une entreprise n'y entre que publiée (Entreprise.date_publication
    non nul, vérifié par app/institution/projets.py, pas ici) — un Chercheur affecté au projet ne
    peut construire une analyse qu'avec des entreprises présentes dans cette table, jamais
    n'importe quelle entreprise publiée de la plateforme."""

    __tablename__ = "projet_entreprise"
    __table_args__ = (
        UniqueConstraint("projet_id", "entreprise_id", name="uq_projet_entreprise"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    projet_id: uuid.UUID = Field(foreign_key="projet.id")
    entreprise_id: uuid.UUID = Field(foreign_key="entreprise.id")
    date_ajout: datetime = Field(default_factory=utcnow)

    projet: Projet = Relationship(back_populates="perimetre")
    entreprise: "Entreprise" = Relationship()


class ProjetDocument(SQLModel, table=True):
    """Les documents explicitement mis à disposition d'un projet (Étape 17bis) — un niveau plus
    restrictif que le périmètre (ProjetEntreprise) : appartenir au périmètre ne rend pas
    automatiquement tous les rapports internes de l'entreprise accessibles, seul un rapport
    explicitement ajouté ici l'est. N'accepte que le rapport actuellement publié de l'entreprise
    (voir app/institution/projets.py::ajouter_document, jamais seulement statut == VALIDE — un
    ancien rapport validé puis remplacé ne doit jamais redevenir accessible ainsi)."""

    __tablename__ = "projet_document"
    __table_args__ = (UniqueConstraint("projet_id", "rapport_id", name="uq_projet_document"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    projet_id: uuid.UUID = Field(foreign_key="projet.id")
    rapport_id: uuid.UUID = Field(foreign_key="rapport_esg.id")
    date_ajout: datetime = Field(default_factory=utcnow)

    projet: Projet = Relationship(back_populates="documents")
    rapport: "RapportESG" = Relationship()
