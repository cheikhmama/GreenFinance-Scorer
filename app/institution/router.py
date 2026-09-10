"""Routes HTTP de l'espace Institution (Étape 17).

Invitation d'un chercheur, gestion des projets/affectations, décision sur une analyse soumise et
export. La logique vit dans app/institution/{chercheurs,projets,analyses}.py — ce router ne fait
qu'appliquer le contrôle d'accès par rôle et l'appeler.
"""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, col, select

from app.auth.models import Utilisateur
from app.auth.permissions import require_role
from app.core.dependencies import get_session
from app.core.enums import Role, StatutRattachement
from app.institution import analyses, chercheurs, projets
from app.institution.models import AffectationProjet, Projet
from app.institution.schemas import (
    AffectationPublic,
    AffecterChercheurRequest,
    AnalyseResume,
    ChercheurDisponible,
    CreerProjetRequest,
    DecisionAnalyseRequest,
    InviterChercheurRequest,
    ProjetDetail,
    ProjetPublic,
    RattachementPublic,
)
from app.researcher.analyses import lister_entreprise_ids
from app.researcher.models import Analyse
from app.researcher.schemas import AnalyseDetail, AnalysePublic

router = APIRouter(tags=["institution"])


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
):
    return chercheurs.inviter_chercheur(session, current_user.id, payload.chercheur_id)


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
):
    return chercheurs.lister_mes_chercheurs(session, current_user.id, statut=statut)


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
    return projets.creer_projet(session, current_user.id, payload.nom, payload.description)


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

    analyses_db = session.exec(select(Analyse).where(col(Analyse.projet_id) == projet.id)).all()
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
    return ProjetDetail(
        **ProjetPublic.model_validate(projet).model_dump(),
        affectations=affectations_out,
        analyses=analyses_out,
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
    affectation = projets.affecter_chercheur(session, current_user.id, projet_id, payload.chercheur_id)
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
    return analyses.valider_analyse(session, current_user.id, analyse_id, payload.commentaire)


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
    return analyses.demander_correction(session, current_user.id, analyse_id, payload.commentaire)


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
        headers={"Content-Disposition": f'attachment; filename="analyse-{analyse_id}.csv"'},
    )
