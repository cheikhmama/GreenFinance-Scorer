"""Routes HTTP de l'espace Chercheur (Étape 17).

Consultation des entreprises publiées (réutilise app/investor/entreprises.py, interface déjà
publique — voir ARCHITECTURE.md §1), réponse aux invitations d'institution, et cycle de vie des
analyses sur les projets affectés. La logique vit dans app/researcher/{rattachements,projets,
analyses}.py — ce router ne fait qu'appliquer le contrôle d'accès par rôle et l'appeler.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, select

from app.auth.models import ChercheurInstitution, Utilisateur
from app.auth.permissions import require_role
from app.core.dependencies import get_session
from app.core.enums import Role
from app.core.exceptions import NotFoundError
from app.core.schemas import Page
from app.institution.schemas import RattachementPublic
from app.investor import entreprises
from app.investor.schemas import EntrepriseDetailInvestisseur, EntreprisePublieePublic
from app.researcher import analyses, projets, rattachements
from app.researcher.models import Analyse
from app.researcher.schemas import (
    AnalyseDetail,
    AnalysePublic,
    CreerAnalyseRequest,
    ModifierAnalyseRequest,
    ProjetAffecte,
)

router = APIRouter(tags=["researcher"])


@router.get(
    "/researcher/entreprises",
    response_model=Page[EntreprisePublieePublic],
    operation_id="listPublishedCompaniesForResearcher",
    summary="Lister les entreprises publiées, avec leur score ESG et leurs émissions Scope 1/2/3",
)
def lister_entreprises_route(
    secteur: str | None = None,
    pays: str | None = None,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> Page[EntreprisePublieePublic]:
    items, total = entreprises.lister_entreprises_publiees(
        session, secteur=secteur, pays=pays, recherche=recherche, page=page, page_size=page_size
    )
    return Page[EntreprisePublieePublic](
        items=items, page=page, page_size=page_size, total=total, pages=-(-total // page_size) or 1
    )


@router.get(
    "/researcher/entreprises/{entreprise_id}",
    response_model=EntrepriseDetailInvestisseur,
    operation_id="getPublishedCompanyDetailForResearcher",
    summary="Consulter le détail d'une entreprise publiée (indicateurs, carbone, preuves)",
)
def consulter_entreprise_route(
    entreprise_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> EntrepriseDetailInvestisseur:
    return entreprises.consulter_entreprise_publiee(session, entreprise_id)


@router.get(
    "/researcher/comparaison",
    response_model=list[EntreprisePublieePublic],
    operation_id="compareCompaniesForResearcher",
    summary="Comparer plusieurs entreprises publiées (score, Scope 1/2/3)",
)
def comparer_entreprises_route(
    entreprise_ids: list[uuid.UUID] = Query(...),
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> list[EntreprisePublieePublic]:
    return entreprises.comparer_entreprises(session, entreprise_ids)


@router.get(
    "/researcher/rattachements",
    response_model=list[RattachementPublic],
    operation_id="listMyInstitutionInvitations",
    summary="Lister les invitations reçues d'institutions",
)
def lister_mes_rattachements_route(
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> list[ChercheurInstitution]:
    return rattachements.lister_mes_rattachements(session, current_user.id)


@router.post(
    "/researcher/rattachements/{rattachement_id}/accepter",
    response_model=RattachementPublic,
    operation_id="acceptInstitutionInvitation",
    summary="Accepter une invitation d'institution",
)
def accepter_rattachement_route(
    rattachement_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> ChercheurInstitution:
    return rattachements.accepter_invitation(session, current_user.id, rattachement_id)


@router.post(
    "/researcher/rattachements/{rattachement_id}/refuser",
    response_model=RattachementPublic,
    operation_id="declineInstitutionInvitation",
    summary="Refuser une invitation d'institution",
)
def refuser_rattachement_route(
    rattachement_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> ChercheurInstitution:
    return rattachements.refuser_invitation(session, current_user.id, rattachement_id)


@router.get(
    "/researcher/projets",
    response_model=list[ProjetAffecte],
    operation_id="listMyAssignedProjects",
    summary="Lister les projets sur lesquels je suis affecté",
)
def lister_mes_projets_route(
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> list[ProjetAffecte]:
    mes_projets = projets.lister_mes_projets(session, current_user.id)
    resultat = []
    for projet in mes_projets:
        institution = session.get(Utilisateur, projet.institution_id)
        resultat.append(
            ProjetAffecte(
                id=projet.id,
                nom=projet.nom,
                description=projet.description,
                statut=projet.statut,
                institution_email=institution.email if institution else "",
            )
        )
    return resultat


def _analyse_detail(session: Session, analyse: Analyse) -> AnalyseDetail:
    return AnalyseDetail(
        **AnalysePublic.model_validate(analyse).model_dump(),
        entreprise_ids=analyses.lister_entreprise_ids(session, analyse.id),
    )


@router.post(
    "/researcher/projets/{projet_id}/analyses",
    response_model=AnalyseDetail,
    status_code=201,
    operation_id="createAnalysis",
    summary="Créer une analyse (brouillon) sur un projet affecté",
)
def creer_analyse_route(
    projet_id: uuid.UUID,
    payload: CreerAnalyseRequest,
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    analyse = analyses.creer_analyse(
        session, current_user.id, projet_id, payload.titre, payload.contenu, payload.entreprise_ids
    )
    return _analyse_detail(session, analyse)


@router.get(
    "/researcher/analyses",
    response_model=list[AnalysePublic],
    operation_id="listMyAnalyses",
    summary="Lister mes analyses, tous projets confondus",
)
def lister_mes_analyses_route(
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> list[Analyse]:
    return list(
        session.exec(select(Analyse).where(col(Analyse.chercheur_id) == current_user.id)).all()
    )


def _analyse_ou_404(session: Session, chercheur_id: uuid.UUID, analyse_id: uuid.UUID) -> Analyse:
    analyse = session.get(Analyse, analyse_id)
    if analyse is None or analyse.chercheur_id != chercheur_id:
        raise NotFoundError("Analyse introuvable.", code="analyse_introuvable")
    return analyse


@router.get(
    "/researcher/analyses/{analyse_id}",
    response_model=AnalyseDetail,
    operation_id="getAnalysisDetail",
    summary="Consulter le détail d'une analyse (statut, décision de l'institution)",
)
def consulter_analyse_route(
    analyse_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    analyse = _analyse_ou_404(session, current_user.id, analyse_id)
    return _analyse_detail(session, analyse)


@router.patch(
    "/researcher/analyses/{analyse_id}",
    response_model=AnalyseDetail,
    operation_id="updateAnalysis",
    summary="Modifier une analyse encore en brouillon",
)
def modifier_analyse_route(
    analyse_id: uuid.UUID,
    payload: ModifierAnalyseRequest,
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    analyse = analyses.modifier_analyse(
        session, current_user.id, analyse_id, payload.titre, payload.contenu, payload.entreprise_ids
    )
    return _analyse_detail(session, analyse)


@router.post(
    "/researcher/analyses/{analyse_id}/soumettre",
    response_model=AnalyseDetail,
    operation_id="submitAnalysis",
    summary="Soumettre une analyse à la décision de l'institution",
)
def soumettre_analyse_route(
    analyse_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    analyse = analyses.soumettre_analyse(session, current_user.id, analyse_id)
    return _analyse_detail(session, analyse)


@router.post(
    "/researcher/analyses/{analyse_id}/corriger",
    response_model=AnalyseDetail,
    status_code=201,
    operation_id="correctAnalysis",
    summary="Créer une nouvelle version d'une analyse suite à une correction demandée",
)
def corriger_analyse_route(
    analyse_id: uuid.UUID,
    payload: ModifierAnalyseRequest,
    current_user: Utilisateur = Depends(require_role(Role.CHERCHEUR)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    nouvelle = analyses.corriger_analyse(
        session, current_user.id, analyse_id, payload.titre, payload.contenu, payload.entreprise_ids
    )
    return _analyse_detail(session, nouvelle)
