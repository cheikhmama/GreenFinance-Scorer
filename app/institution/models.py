"""Entités de persistance de l'espace Institution : projets et affectations (Étape 17).

Un Projet est créé par une Institution et peut affecter plusieurs Chercheurs (chacun avec son
propre fil d'analyse, voir app/researcher/models.py::Analysis) — jamais l'inverse, un Chercheur ne
crée jamais de projet. L'affectation exige un rattachement ResearcherAffiliation déjà ACCEPTE
(vérifié par app/institution/projets.py, pas ici : ce module ne pose que le schéma).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import ProjectStatus, sa_enum_column

if TYPE_CHECKING:
    from app.auth.models import User
    from app.company.models import Company
    from app.ingestion.models import ESGReport
    from app.researcher.models import Analysis


class Project(SQLModel, table=True):
    """Table `projects` (tâche 4.7)."""

    __tablename__ = "projects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    institution_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    name: str
    description: str | None = None
    # Distinct de description (texte libre) : objective porte la finalité de la mission, demandée
    # explicitement comme champ séparé (Étape 17bis).
    objective: str | None = None
    # Période prévue du projet (start_date -> planned_end_date) et échéance de remise du travail
    # (deadline, optionnelle, distincte de la fin de période) — toutes trois de simples
    # intentions posées par l'Institution, jamais recalculées. closed_at (ci-dessous) reste la
    # seule date à valeur réelle : la date effective de clôture.
    start_date: datetime | None = None
    planned_end_date: datetime | None = None
    deadline: datetime | None = None
    status: ProjectStatus = Field(
        default=ProjectStatus.OUVERT, sa_column=sa_enum_column(ProjectStatus)
    )
    created_at: datetime = Field(default_factory=utcnow)
    # Nulle tant que le projet est OUVERT — renseignée une seule fois à la clôture, jamais
    # recalculée (même principe que Company.published_at).
    closed_at: datetime | None = None

    institution: "User" = Relationship(back_populates="projects")
    assignments: list["ProjectAssignment"] = Relationship(back_populates="project")
    analyses: list["Analysis"] = Relationship(back_populates="project")
    companies: list["ProjectCompany"] = Relationship(back_populates="project")
    documents: list["ProjectDocument"] = Relationship(back_populates="project")


class ProjectAssignment(SQLModel, table=True):
    """Chercheur affecté à un projet. Table `project_assignments` (tâche 4.7)."""

    __tablename__ = "project_assignments"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "researcher_id", name="uq_project_assignments_project_researcher"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # CASCADE : une affectation n'existe qu'avec son projet. Index fourni par l'unicité.
    project_id: uuid.UUID = Field(foreign_key="projects.id", ondelete="CASCADE")
    researcher_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    assigned_at: datetime = Field(default_factory=utcnow)

    project: Project = Relationship(back_populates="assignments")
    researcher: "User" = Relationship(back_populates="project_assignments")


class ProjectCompany(SQLModel, table=True):
    """Périmètre d'un projet : les entreprises publiées que ses chercheurs peuvent consulter
    (app/researcher/projets.py::entreprises_perimetre_chercheur). Table `project_companies`."""

    __tablename__ = "project_companies"
    __table_args__ = (
        UniqueConstraint("project_id", "company_id", name="uq_project_companies_project_company"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", ondelete="CASCADE")
    company_id: uuid.UUID = Field(foreign_key="companies.id", ondelete="CASCADE", index=True)
    added_at: datetime = Field(default_factory=utcnow)

    project: Project = Relationship(back_populates="companies")
    company: "Company" = Relationship()


class ProjectDocument(SQLModel, table=True):
    """Rapport publié joint à un projet. Table `project_documents` (tâche 4.7)."""

    __tablename__ = "project_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "report_id", name="uq_project_documents_project_report"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", ondelete="CASCADE")
    report_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE", index=True)
    added_at: datetime = Field(default_factory=utcnow)

    project: Project = Relationship(back_populates="documents")
    report: "ESGReport" = Relationship()
