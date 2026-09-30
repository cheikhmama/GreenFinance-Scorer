"""Schémas Pydantic d'entrée/sortie du module Institution.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2). RattachementPublic est
défini ici (l'Institution est l'initiatrice de l'invitation) et réutilisé par
app/researcher/schemas.py pour la même relation vue côté Chercheur.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.auth.schemas import UserContractMixin
from app.core.enums import AffiliationStatus, AnalysisStatus, ProjectStatus


class ChercheurDisponible(UserContractMixin):
    """Compte CHERCHEUR actif, sélectionnable pour une invitation — même règle "sélection parmi
    les acteurs existants" que partout ailleurs (jamais de saisie libre d'identité)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None


class InviterChercheurRequest(BaseModel):
    researcher_id: uuid.UUID
    collaboration_terms: str | None = None


class RattachementPublic(BaseModel):
    id: uuid.UUID
    researcher_id: uuid.UUID
    # Dénormalisés depuis Utilisateur au moment de la construction (voir
    # app/institution/router.py::rattachement_public) — jamais une jointure ORM directe, la
    # table de rattachement elle-même ne porte que chercheur_id/institution_id (voir
    # app/auth/models.py). Les deux côtés (Institution consultant ses chercheurs, Chercheur
    # consultant ses institutions) ont symétriquement besoin de savoir qui est qui.
    researcher_email: str
    researcher_name: str | None
    institution_id: uuid.UUID
    institution_email: str
    institution_name: str | None
    status: AffiliationStatus
    invited_at: datetime
    responded_at: datetime | None
    collaboration_terms: str | None


class CreerProjetRequest(BaseModel):
    name: str
    description: str | None = None
    objective: str | None = None
    start_date: datetime | None = None
    planned_end_date: datetime | None = None
    deadline: datetime | None = None


class AffecterChercheurRequest(BaseModel):
    researcher_id: uuid.UUID


class DecisionAnalyseRequest(BaseModel):
    comment: str | None = None


class AjouterEntreprisePerimetreRequest(BaseModel):
    company_id: uuid.UUID


class AjouterDocumentRequest(BaseModel):
    report_id: uuid.UUID


class EntreprisePerimetrePublic(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str
    # Rapport actuellement publié de l'entreprise (dernier_rapport_valide), s'il existe — c'est le
    # seul rapport_id qu'ajouter_document acceptera pour cette entreprise (voir
    # app/institution/projets.py::ajouter_document). Nul si l'entreprise n'a encore aucun rapport
    # validé, ce qui ne devrait pas arriver pour une entreprise publiée mais reste possible en
    # théorie (voir Company.published_at, jamais garanti par une contrainte SQL).
    latest_report_id: uuid.UUID | None
    added_at: datetime


class DocumentProjetPublic(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    company_id: uuid.UUID
    company_name: str
    fiscal_year: int | None
    added_at: datetime


class ProjetPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    name: str
    description: str | None
    objective: str | None
    start_date: datetime | None
    planned_end_date: datetime | None
    deadline: datetime | None
    status: ProjectStatus
    created_at: datetime
    closed_at: datetime | None


class AffectationPublic(BaseModel):
    id: uuid.UUID
    researcher_id: uuid.UUID
    researcher_email: str
    assigned_at: datetime


class AnalyseResume(BaseModel):
    id: uuid.UUID
    researcher_id: uuid.UUID
    title: str
    status: AnalysisStatus
    version: int
    created_at: datetime
    submitted_at: datetime | None


class AnalyseInstitutionPublic(AnalyseResume):
    """AnalyseResume enrichi du projet d'origine — nécessaire ici (contrairement à
    ProjetDetail.analyses) puisque cette liste traverse tous les projets de l'institution à la
    fois, voir app/institution/router.py::lister_mes_analyses_route."""

    project_id: uuid.UUID
    project_name: str


class ProjetDetail(ProjetPublic):
    assignments: list[AffectationPublic]
    analyses: list[AnalyseResume]
    companies: list[EntreprisePerimetrePublic]
    documents: list[DocumentProjetPublic]


class InstitutionProfilPublic(BaseModel):
    """Lecture seule — quota_export n'est jamais modifié ici, seulement consommé par
    app/institution/analyses.py::_consommer_quota_export au fil des exports réels."""

    export_quota: int
