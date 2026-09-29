"""Schémas Pydantic d'entrée/sortie du module Institution.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2). RattachementPublic est
défini ici (l'Institution est l'initiatrice de l'invitation) et réutilisé par
app/researcher/schemas.py pour la même relation vue côté Chercheur.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.auth.schemas import UserContractMixin
from app.core.enums import StatutAnalyse, StatutProjet, StatutRattachement


class ChercheurDisponible(UserContractMixin):
    """Compte CHERCHEUR actif, sélectionnable pour une invitation — même règle "sélection parmi
    les acteurs existants" que partout ailleurs (jamais de saisie libre d'identité)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nom: str | None


class InviterChercheurRequest(BaseModel):
    chercheur_id: uuid.UUID
    conditions_collaboration: str | None = None


class RattachementPublic(BaseModel):
    id: uuid.UUID
    chercheur_id: uuid.UUID
    # Dénormalisés depuis Utilisateur au moment de la construction (voir
    # app/institution/router.py::rattachement_public) — jamais une jointure ORM directe, la
    # table de rattachement elle-même ne porte que chercheur_id/institution_id (voir
    # app/auth/models.py). Les deux côtés (Institution consultant ses chercheurs, Chercheur
    # consultant ses institutions) ont symétriquement besoin de savoir qui est qui.
    chercheur_email: str
    chercheur_nom: str | None
    institution_id: uuid.UUID
    institution_email: str
    institution_nom: str | None
    statut: StatutRattachement
    date_invitation: datetime
    date_reponse: datetime | None
    conditions_collaboration: str | None


class CreerProjetRequest(BaseModel):
    nom: str
    description: str | None = None
    objectif: str | None = None
    date_debut: datetime | None = None
    date_fin_prevue: datetime | None = None
    date_limite: datetime | None = None


class AffecterChercheurRequest(BaseModel):
    chercheur_id: uuid.UUID


class DecisionAnalyseRequest(BaseModel):
    commentaire: str | None = None


class AjouterEntreprisePerimetreRequest(BaseModel):
    entreprise_id: uuid.UUID


class AjouterDocumentRequest(BaseModel):
    rapport_id: uuid.UUID


class EntreprisePerimetrePublic(BaseModel):
    id: uuid.UUID
    entreprise_id: uuid.UUID
    entreprise_nom: str
    # Rapport actuellement publié de l'entreprise (dernier_rapport_valide), s'il existe — c'est le
    # seul rapport_id qu'ajouter_document acceptera pour cette entreprise (voir
    # app/institution/projets.py::ajouter_document). Nul si l'entreprise n'a encore aucun rapport
    # validé, ce qui ne devrait pas arriver pour une entreprise publiée mais reste possible en
    # théorie (voir Company.published_at, jamais garanti par une contrainte SQL).
    dernier_rapport_id: uuid.UUID | None
    date_ajout: datetime


class DocumentProjetPublic(BaseModel):
    id: uuid.UUID
    rapport_id: uuid.UUID
    entreprise_id: uuid.UUID
    entreprise_nom: str
    annee_reporting: int | None
    date_ajout: datetime


class ProjetPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    nom: str
    description: str | None
    objectif: str | None
    date_debut: datetime | None
    date_fin_prevue: datetime | None
    date_limite: datetime | None
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


class AnalyseInstitutionPublic(AnalyseResume):
    """AnalyseResume enrichi du projet d'origine — nécessaire ici (contrairement à
    ProjetDetail.analyses) puisque cette liste traverse tous les projets de l'institution à la
    fois, voir app/institution/router.py::lister_mes_analyses_route."""

    projet_id: uuid.UUID
    projet_nom: str


class ProjetDetail(ProjetPublic):
    affectations: list[AffectationPublic]
    analyses: list[AnalyseResume]
    perimetre: list[EntreprisePerimetrePublic]
    documents: list[DocumentProjetPublic]


class InstitutionProfilPublic(BaseModel):
    """Lecture seule — quota_export n'est jamais modifié ici, seulement consommé par
    app/institution/analyses.py::_consommer_quota_export au fil des exports réels."""

    quota_export: int
