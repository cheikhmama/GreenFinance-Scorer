"""Entités de persistance de l'espace Chercheur : analyses (Étape 17).

Une Analyse est toujours rattachée à un Projet (app/institution/models.py) et à l'Affectation qui
en donne le droit — jamais créée hors projet. Une correction demandée par l'Institution ne
réécrit jamais l'analyse existante : elle reste CORRECTION_DEMANDEE, et une nouvelle ligne est
créée avec version+1 et analyse_precedente_id pointant vers elle (même principe que
app/ingestion/models.py::ESGReport). Statut + commentaire_institution suffisent ici, sans
entité "avis" séparée comme AvisAudit : un seul acteur (l'Institution) décide, il n'y a pas de
recommandation intermédiaire d'un tiers à tracer séparément.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import StatutAnalyse, sa_enum_column

if TYPE_CHECKING:
    from app.auth.models import User
    from app.company.models import Company
    from app.institution.models import Projet


class Analyse(SQLModel, table=True):
    __tablename__ = "analyse"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    projet_id: uuid.UUID = Field(foreign_key="projet.id")
    chercheur_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    titre: str
    contenu: str
    statut: StatutAnalyse = Field(
        default=StatutAnalyse.BROUILLON, sa_column=sa_enum_column(StatutAnalyse)
    )
    version: int = Field(default=1)
    analyse_precedente_id: uuid.UUID | None = Field(default=None, foreign_key="analyse.id")
    commentaire_institution: str | None = None
    date_creation: datetime = Field(default_factory=utcnow)
    date_soumission: datetime | None = None
    date_decision: datetime | None = None

    projet: "Projet" = Relationship(back_populates="analyses")
    chercheur: "User" = Relationship(back_populates="analyses")
    entreprises: list["AnalyseEntreprise"] = Relationship(back_populates="analyse")


class AnalyseEntreprise(SQLModel, table=True):
    """Entreprises publiées comparées dans une analyse — jamais l'entreprise brute, toujours via
    ce lien explicite (une analyse peut en comparer plusieurs)."""

    __tablename__ = "analyse_entreprise"
    __table_args__ = (
        UniqueConstraint("analyse_id", "entreprise_id", name="uq_analyse_entreprise"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    analyse_id: uuid.UUID = Field(foreign_key="analyse.id")
    entreprise_id: uuid.UUID = Field(foreign_key="companies.id", ondelete="CASCADE", index=True)
    # Figés au moment de l'ajout (jamais fournis par le Chercheur, jamais mis à jour ensuite) :
    # rapport_id fixe le rapport publié exact (indicateurs, Scope 1/2/3, preuves), score_esg_id le
    # score E/S/G/global + méthodologie/version exacts (app/scoring/engine.py::score_officiel).
    # Une réévaluation ou republication ultérieure de l'entreprise ne change jamais ces deux
    # valeurs : l'analyse restitue toujours ce qui a réellement été utilisé à sa création.
    rapport_id: uuid.UUID | None = Field(
        default=None, foreign_key="esg_reports.id", ondelete="SET NULL", index=True
    )
    # SET NULL (tâche 3.1) : comme rapport_id, la suppression d'un rapport — et donc de ses scores
    # — ne doit jamais être bloquée par une analyse qui l'a figé.
    score_esg_id: uuid.UUID | None = Field(
        default=None, foreign_key="scores.id", ondelete="SET NULL", index=True
    )

    analyse: Analyse = Relationship(back_populates="entreprises")
    entreprise: Optional["Company"] = Relationship()
