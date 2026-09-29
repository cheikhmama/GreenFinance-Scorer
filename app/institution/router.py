"""Routes HTTP de l'espace Institution (Étape 17).

Invitation d'un chercheur, gestion des projets/affectations, décision sur une analyse soumise et
export. La logique vit dans app/institution/{chercheurs,projets,analyses}.py — ce router ne fait
qu'appliquer le contrôle d'accès par rôle et l'appeler.
"""

import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, col, select

from app.auth.models import ChercheurInstitution, InstitutionProfil, Utilisateur
from app.auth.permissions import require_role
from app.core import storage
from app.core.dependencies import get_session
from app.core.enums import Role, StatutAnalyse, StatutRattachement
from app.core.schemas import Page
from app.institution import analyses, chercheurs, projets
from app.institution.models import (
    AffectationProjet,
    Projet,
    ProjetDocument,
    ProjetEntreprise,
)
from app.institution.schemas import (
    AffectationPublic,
    AffecterChercheurRequest,
    AjouterDocumentRequest,
    AjouterEntreprisePerimetreRequest,
    AnalyseInstitutionPublic,
    AnalyseResume,
    ChercheurDisponible,
    CreerProjetRequest,
    DecisionAnalyseRequest,
    DocumentProjetPublic,
    EntreprisePerimetrePublic,
    InstitutionProfilPublic,
    InviterChercheurRequest,
    ProjetDetail,
    ProjetPublic,
    RattachementPublic,
)
from app.investor import entreprises as entreprises_publiees
from app.investor.schemas import EntrepriseDetailInvestisseur, EntreprisePublieePublic
from app.researcher.analyses import lister_entreprise_ids
from app.researcher.models import Analyse
from app.researcher.schemas import AnalyseDetail, AnalysePublic

router = APIRouter(tags=["institution"])


def rattachement_public(
    session: Session, rattachement: ChercheurInstitution
) -> RattachementPublic:
    """Dénormalise l'e-mail/nom du Chercheur ET de l'Institution — ChercheurInstitution ne porte
    que chercheur_id/institution_id, jamais de jointure ORM directe vers Utilisateur (voir
    app/auth/models.py). Réutilisé par app/researcher/router.py pour la même relation vue côté
    Chercheur (qui a symétriquement besoin de savoir quelle institution l'a invité)."""
    chercheur = session.get(Utilisateur, rattachement.chercheur_id)
    institution = session.get(Utilisateur, rattachement.institution_id)
    return RattachementPublic(
        id=rattachement.id,
        chercheur_id=rattachement.chercheur_id,
        chercheur_email=chercheur.email if chercheur else "",
        chercheur_nom=chercheur.nom if chercheur else None,
        institution_id=rattachement.institution_id,
        institution_email=institution.email if institution else "",
        institution_nom=institution.nom if institution else None,
        statut=rattachement.statut,
        date_invitation=rattachement.date_invitation,
        date_reponse=rattachement.date_reponse,
        conditions_collaboration=rattachement.conditions_collaboration,
    )


def entreprise_perimetre_public(
    session: Session, lien: ProjetEntreprise
) -> EntreprisePerimetrePublic:
    """dernier_rapport_id est le seul rapport qu'ajouter_document acceptera pour cette entreprise
    (voir app/institution/projets.py::ajouter_document) — jamais déduit côté frontend."""
    rapport = entreprises_publiees.dernier_rapport_valide(session, lien.entreprise_id)
    return EntreprisePerimetrePublic(
        id=lien.id,
        entreprise_id=lien.entreprise_id,
        entreprise_nom=lien.entreprise.name,
        dernier_rapport_id=rapport.id if rapport else None,
        date_ajout=lien.date_ajout,
    )


@router.get(
    "/institution/profil",
    response_model=InstitutionProfilPublic,
    operation_id="getMyInstitutionProfile",
    summary="Consulter mon quota d'export restant",
)
def consulter_mon_profil_route(
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> InstitutionProfil:
    return analyses.consulter_mon_profil(session, current_user.id)


@router.get(
    "/institution/chercheurs/disponibles",
    response_model=list[ChercheurDisponible],
    operation_id="listAvailableResearchers",
    summary="Lister les comptes Chercheur disponibles à inviter",
)
def lister_chercheurs_disponibles_route(
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> list[Utilisateur]:
    return chercheurs.lister_chercheurs_disponibles(session, current_user.id)


@router.post(
    "/institution/chercheurs/inviter",
    response_model=RattachementPublic,
    status_code=201,
    operation_id="inviteResearcher",
    summary="Inviter un chercheur",
)
def inviter_chercheur_route(
    payload: InviterChercheurRequest,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> RattachementPublic:
    rattachement = chercheurs.inviter_chercheur(
        session, current_user.id, payload.chercheur_id, payload.conditions_collaboration
    )
    return rattachement_public(session, rattachement)


@router.get(
    "/institution/chercheurs",
    response_model=list[RattachementPublic],
    operation_id="listMyResearchers",
    summary="Lister mes rattachements chercheurs (invités, acceptés, refusés)",
)
def lister_mes_chercheurs_route(
    statut: StatutRattachement | None = None,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> list[RattachementPublic]:
    rattachements = chercheurs.lister_mes_chercheurs(
        session, current_user.id, statut=statut
    )
    return [rattachement_public(session, r) for r in rattachements]


@router.get(
    "/institution/entreprises",
    response_model=Page[EntreprisePublieePublic],
    operation_id="listPublishedCompaniesForInstitution",
    summary="Lister les entreprises publiées, pour composer le périmètre d'un projet",
)
def lister_entreprises_route(
    secteur: str | None = None,
    pays: str | None = None,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> Page[EntreprisePublieePublic]:
    items, total = entreprises_publiees.lister_entreprises_publiees(
        session,
        secteur=secteur,
        pays=pays,
        recherche=recherche,
        page=page,
        page_size=page_size,
    )
    return Page[EntreprisePublieePublic](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=-(-total // page_size) or 1,
    )


@router.get(
    "/institution/entreprises/{entreprise_id}",
    response_model=EntrepriseDetailInvestisseur,
    operation_id="getPublishedCompanyDetailForInstitution",
    summary="Consulter le détail d'une entreprise publiée (indicateurs, carbone, preuves)",
)
def consulter_entreprise_route(
    entreprise_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> EntrepriseDetailInvestisseur:
    perimetre = projets.entreprises_perimetre_institution(session, current_user.id)
    return entreprises_publiees.consulter_entreprise_publiee(
        session, entreprise_id, perimetre_autorise=perimetre
    )


@router.get(
    "/institution/entreprises/{entreprise_id}/preuves/{preuve_id}/fichier",
    operation_id="getEvidenceFileForInstitution",
    summary="Consulter l'extrait PDF (une page) prouvant un indicateur ou une donnée carbone",
)
def consulter_preuve_route(
    entreprise_id: uuid.UUID,
    preuve_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> FileResponse:
    perimetre = projets.entreprises_perimetre_institution(session, current_user.id)
    chemin = entreprises_publiees.fichier_preuve(
        session, entreprise_id, preuve_id, perimetre_autorise=perimetre
    )
    return FileResponse(storage.resolve_path(chemin), media_type="application/pdf")


@router.post(
    "/institution/projets",
    response_model=ProjetPublic,
    status_code=201,
    operation_id="createProject",
    summary="Créer un projet",
)
def creer_projet_route(
    payload: CreerProjetRequest,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> Projet:
    return projets.creer_projet(
        session,
        current_user.id,
        payload.nom,
        payload.description,
        payload.objectif,
        payload.date_debut,
        payload.date_fin_prevue,
        payload.date_limite,
    )


@router.get(
    "/institution/projets",
    response_model=list[ProjetPublic],
    operation_id="listMyProjects",
    summary="Lister mes projets",
)
def lister_mes_projets_route(
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> list[Projet]:
    return projets.lister_mes_projets(session, current_user.id)


def _projet_detail(session: Session, projet: Projet) -> ProjetDetail:
    affectations_db = session.exec(
        select(AffectationProjet).where(col(AffectationProjet.projet_id) == projet.id)
    ).all()
    affectations_out = []
    for affectation in affectations_db:
        chercheur = session.get(Utilisateur, affectation.chercheur_id)
        affectations_out.append(
            AffectationPublic(
                id=affectation.id,
                chercheur_id=affectation.chercheur_id,
                chercheur_email=chercheur.email if chercheur else "",
                date_affectation=affectation.date_affectation,
            )
        )

    analyses_db = session.exec(
        select(Analyse).where(col(Analyse.projet_id) == projet.id)
    ).all()
    analyses_out = [
        AnalyseResume(
            id=a.id,
            chercheur_id=a.chercheur_id,
            titre=a.titre,
            statut=a.statut,
            version=a.version,
            date_creation=a.date_creation,
            date_soumission=a.date_soumission,
        )
        for a in analyses_db
    ]

    perimetre_db = session.exec(
        select(ProjetEntreprise).where(col(ProjetEntreprise.projet_id) == projet.id)
    ).all()
    perimetre_out = [
        entreprise_perimetre_public(session, lien) for lien in perimetre_db
    ]

    documents_db = session.exec(
        select(ProjetDocument).where(col(ProjetDocument.projet_id) == projet.id)
    ).all()
    documents_out = [
        DocumentProjetPublic(
            id=document.id,
            rapport_id=document.rapport_id,
            entreprise_id=document.rapport.company_id,
            entreprise_nom=document.rapport.company.name,
            annee_reporting=document.rapport.fiscal_year,
            date_ajout=document.date_ajout,
        )
        for document in documents_db
    ]

    return ProjetDetail(
        **ProjetPublic.model_validate(projet).model_dump(),
        affectations=affectations_out,
        analyses=analyses_out,
        perimetre=perimetre_out,
        documents=documents_out,
    )


@router.get(
    "/institution/projets/{projet_id}",
    response_model=ProjetDetail,
    operation_id="getProjectDetail",
    summary="Consulter le détail d'un projet (chercheurs affectés, analyses)",
)
def consulter_projet_route(
    projet_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> ProjetDetail:
    projet = projets.consulter_projet(session, current_user.id, projet_id)
    return _projet_detail(session, projet)


@router.post(
    "/institution/projets/{projet_id}/affecter",
    response_model=AffectationPublic,
    status_code=201,
    operation_id="assignResearcherToProject",
    summary="Affecter un chercheur accepté à un projet",
)
def affecter_chercheur_route(
    projet_id: uuid.UUID,
    payload: AffecterChercheurRequest,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> AffectationPublic:
    affectation = projets.affecter_chercheur(
        session, current_user.id, projet_id, payload.chercheur_id
    )
    chercheur = session.get(Utilisateur, payload.chercheur_id)
    return AffectationPublic(
        id=affectation.id,
        chercheur_id=affectation.chercheur_id,
        chercheur_email=chercheur.email if chercheur else "",
        date_affectation=affectation.date_affectation,
    )


@router.post(
    "/institution/projets/{projet_id}/cloturer",
    response_model=ProjetPublic,
    operation_id="closeProject",
    summary="Clôturer un projet",
)
def cloturer_projet_route(
    projet_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> Projet:
    return projets.cloturer_projet(session, current_user.id, projet_id)


@router.post(
    "/institution/projets/{projet_id}/perimetre",
    response_model=EntreprisePerimetrePublic,
    status_code=201,
    operation_id="addCompanyToProjectScope",
    summary="Ajouter une entreprise publiée au périmètre autorisé du projet",
)
def ajouter_entreprise_perimetre_route(
    projet_id: uuid.UUID,
    payload: AjouterEntreprisePerimetreRequest,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> EntreprisePerimetrePublic:
    lien = projets.ajouter_entreprise_perimetre(
        session, current_user.id, projet_id, payload.entreprise_id
    )
    return entreprise_perimetre_public(session, lien)


@router.get(
    "/institution/projets/{projet_id}/perimetre",
    response_model=list[EntreprisePerimetrePublic],
    operation_id="listProjectScope",
    summary="Lister les entreprises autorisées dans le périmètre du projet",
)
def lister_perimetre_route(
    projet_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> list[EntreprisePerimetrePublic]:
    liens = projets.lister_perimetre(session, current_user.id, projet_id)
    return [entreprise_perimetre_public(session, lien) for lien in liens]


@router.post(
    "/institution/projets/{projet_id}/documents",
    response_model=DocumentProjetPublic,
    status_code=201,
    operation_id="addDocumentToProject",
    summary="Mettre à disposition le rapport publié d'une entreprise du périmètre",
)
def ajouter_document_route(
    projet_id: uuid.UUID,
    payload: AjouterDocumentRequest,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> DocumentProjetPublic:
    document = projets.ajouter_document(
        session, current_user.id, projet_id, payload.rapport_id
    )
    return DocumentProjetPublic(
        id=document.id,
        rapport_id=document.rapport_id,
        entreprise_id=document.rapport.company_id,
        entreprise_nom=document.rapport.company.name,
        annee_reporting=document.rapport.fiscal_year,
        date_ajout=document.date_ajout,
    )


@router.get(
    "/institution/projets/{projet_id}/documents",
    response_model=list[DocumentProjetPublic],
    operation_id="listProjectDocuments",
    summary="Lister les documents mis à disposition sur le projet",
)
def lister_documents_route(
    projet_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> list[DocumentProjetPublic]:
    documents = projets.lister_documents(session, current_user.id, projet_id)
    return [
        DocumentProjetPublic(
            id=document.id,
            rapport_id=document.rapport_id,
            entreprise_id=document.rapport.company_id,
            entreprise_nom=document.rapport.company.name,
            annee_reporting=document.rapport.fiscal_year,
            date_ajout=document.date_ajout,
        )
        for document in documents
    ]


@router.get(
    "/institution/analyses",
    response_model=list[AnalyseInstitutionPublic],
    operation_id="listMyAnalysesForInstitution",
    summary="Lister mes analyses reçues, tous projets confondus",
)
def lister_mes_analyses_route(
    statut: StatutAnalyse | None = None,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> list[AnalyseInstitutionPublic]:
    mes_analyses = analyses.lister_mes_analyses(session, current_user.id, statut=statut)
    resultat = []
    for analyse in mes_analyses:
        projet = session.get(Projet, analyse.projet_id)
        resultat.append(
            AnalyseInstitutionPublic(
                id=analyse.id,
                chercheur_id=analyse.chercheur_id,
                titre=analyse.titre,
                statut=analyse.statut,
                version=analyse.version,
                date_creation=analyse.date_creation,
                date_soumission=analyse.date_soumission,
                projet_id=analyse.projet_id,
                projet_nom=projet.nom if projet else "",
            )
        )
    return resultat


@router.get(
    "/institution/analyses/{analyse_id}",
    response_model=AnalyseDetail,
    operation_id="getAnalysisDetailForInstitution",
    summary="Consulter le détail d'une analyse soumise sur l'un de mes projets",
)
def consulter_analyse_route(
    analyse_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    analyse = analyses.analyse_de_institution(session, current_user.id, analyse_id)
    return AnalyseDetail(
        **AnalysePublic.model_validate(analyse).model_dump(),
        entreprise_ids=lister_entreprise_ids(session, analyse.id),
    )


@router.post(
    "/institution/analyses/{analyse_id}/valider",
    response_model=AnalysePublic,
    operation_id="approveAnalysis",
    summary="Valider une analyse soumise",
)
def valider_analyse_route(
    analyse_id: uuid.UUID,
    payload: DecisionAnalyseRequest,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
):
    return analyses.valider_analyse(
        session, current_user.id, analyse_id, payload.commentaire
    )


@router.post(
    "/institution/analyses/{analyse_id}/demander-correction",
    response_model=AnalysePublic,
    operation_id="requestAnalysisCorrection",
    summary="Demander une correction sur une analyse soumise",
)
def demander_correction_route(
    analyse_id: uuid.UUID,
    payload: DecisionAnalyseRequest,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
):
    return analyses.demander_correction(
        session, current_user.id, analyse_id, payload.commentaire
    )


@router.get(
    "/institution/analyses/{analyse_id}/historique",
    response_model=list[AnalysePublic],
    operation_id="getAnalysisHistoryForInstitution",
    summary="Reconstruire la chaîne complète des versions d'une analyse (v1 -> correction -> v2 -> ...)",
)
def historique_analyse_route(
    analyse_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> list[Analyse]:
    return analyses.historique_analyse(session, current_user.id, analyse_id)


@router.get(
    "/institution/analyses/{analyse_id}/export",
    operation_id="exportAnalysis",
    summary="Exporter une analyse au format CSV (consomme le quota d'export)",
)
def exporter_analyse_route(
    analyse_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INSTITUTION)),
    session: Session = Depends(get_session),
) -> Response:
    contenu_csv = analyses.exporter_analyse_csv(session, current_user.id, analyse_id)
    return Response(
        content=contenu_csv,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="analyse-{analyse_id}.csv"'
        },
    )
