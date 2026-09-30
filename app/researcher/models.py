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

from sqlalchemy import CheckConstraint, UniqueConstraint
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


class ReferenceDataset(SQLModel, table=True):
    """Jeu de données ESG public importé par un Chercheur pour une validation croisée (tâche 3.3,
    docs/WORKFLOWS.md §3.4) — Kaggle, CDP, GRI ou autre. Zone de préparation : ces données ne
    modifient jamais celles de la plateforme et ne sont visibles que de leur auteur.

    L'échelle et le sens des scores sont déclarés à l'import (un score de risque Sustainalytics
    est « plus bas = meilleur », une note Kaggle peut aller de 0 à 1 000) : ils servent à ramener
    chaque valeur sur l'échelle 0-100 de la plateforme avant tout écart moyen."""

    __tablename__ = "reference_datasets"
    __table_args__ = (
        CheckConstraint("scale_max > scale_min", name="ck_reference_datasets_scale"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    name: str = Field(max_length=200)
    source_url: str = Field(max_length=500)
    licence: str = Field(max_length=200)
    scale_min: float
    scale_max: float
    higher_is_better: bool
    created_at: datetime = Field(default_factory=utcnow)

    rows: list["ReferenceDatasetRow"] = Relationship(
        back_populates="dataset", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class ReferenceDatasetRow(SQLModel, table=True):
    """Une ligne importée, telle que fournie (valeurs brutes, dans l'échelle du jeu de données).
    Au moins un identifiant de marché : le rapprochement se fait par ISIN ou LEI, jamais par nom
    seul — `company_name` n'est qu'informatif."""

    __tablename__ = "reference_dataset_rows"
    __table_args__ = (
        CheckConstraint(
            "isin IS NOT NULL OR lei IS NOT NULL", name="ck_reference_dataset_rows_identifier"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    dataset_id: uuid.UUID = Field(
        foreign_key="reference_datasets.id", ondelete="CASCADE", index=True
    )
    line_number: int
    isin: str | None = Field(default=None, max_length=12)
    lei: str | None = Field(default=None, max_length=20)
    company_name: str | None = Field(default=None, max_length=200)
    environmental_score: float | None = None
    social_score: float | None = None
    governance_score: float | None = None
    total_score: float | None = None

    dataset: ReferenceDataset = Relationship(back_populates="rows")
