"""Routes HTTP de l'espace Investisseur (Étape 15/16).

Consultation des entreprises publiées (score, Scope 1/2/3, preuves), comparaison, tableau de
bord, et gestion des portefeuilles/positions. La logique vit dans app/investor/{entreprises,
portfolio,dashboard}.py — ce router ne fait qu'appliquer le contrôle d'accès par rôle et
appeler cette logique (même convention que les autres espaces, voir ARCHITECTURE.md §2).
"""

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlmodel import Session

from app.auth.models import Utilisateur
from app.auth.permissions import require_role
from app.core.dependencies import get_session
from app.core.enums import Role
from app.core.exceptions import NotFoundError
from app.core.schemas import Page
from app.investor import dashboard, entreprises, portfolio
from app.investor.models import Portefeuille, PositionPortefeuille
from app.investor.schemas import (
    AjouterPositionRequest,
    CreerPortefeuilleRequest,
    EntrepriseDetailInvestisseur,
    EntreprisePublieePublic,
    FermerPositionRequest,
    ModifierPositionRequest,
    PortefeuilleDetail,
    PortefeuilleResume,
    PositionDetail,
    RenommerPortefeuilleRequest,
    TableauDeBordInvestisseur,
)

router = APIRouter(tags=["investor"])


@router.get(
    "/investor/entreprises",
    response_model=Page[EntreprisePublieePublic],
    operation_id="listPublishedCompanies",
    summary="Lister les entreprises publiées, avec leur score ESG et leurs émissions Scope 1/2/3",
)
def lister_entreprises_route(
    secteur: str | None = None,
    pays: str | None = None,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> Page[EntreprisePublieePublic]:
    items, total = entreprises.lister_entreprises_publiees(
        session, secteur=secteur, pays=pays, recherche=recherche, page=page, page_size=page_size
    )
    return Page[EntreprisePublieePublic](
        items=items, page=page, page_size=page_size, total=total, pages=-(-total // page_size) or 1
    )


@router.get(
    "/investor/entreprises/{entreprise_id}",
    response_model=EntrepriseDetailInvestisseur,
    operation_id="getPublishedCompanyDetail",
    summary="Consulter le détail d'une entreprise publiée (indicateurs, carbone, preuves)",
)
def consulter_entreprise_route(
    entreprise_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> EntrepriseDetailInvestisseur:
    return entreprises.consulter_entreprise_publiee(session, entreprise_id)


@router.get(
    "/investor/comparaison",
    response_model=list[EntreprisePublieePublic],
    operation_id="compareCompanies",
    summary="Comparer plusieurs entreprises publiées (score, Scope 1/2/3)",
)
def comparer_entreprises_route(
    entreprise_ids: list[uuid.UUID] = Query(...),
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> list[EntreprisePublieePublic]:
    return entreprises.comparer_entreprises(session, entreprise_ids)


@router.get(
    "/investor/dashboard",
    response_model=TableauDeBordInvestisseur,
    operation_id="getInvestorDashboard",
    summary="Tableau de bord de l'espace Investisseur",
)
def tableau_de_bord_route(
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> TableauDeBordInvestisseur:
    return dashboard.construire_tableau_de_bord(session, current_user.id)


@router.post(
    "/investor/portefeuilles",
    response_model=PortefeuilleResume,
    status_code=201,
    operation_id="createPortfolio",
    summary="Créer un portefeuille",
)
def creer_portefeuille_route(
    payload: CreerPortefeuilleRequest,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> PortefeuilleResume:
    portefeuille_cree = portfolio.creer_portefeuille(
        session, current_user.id, payload.nom, payload.devise_reference
    )
    return portfolio.resume_portefeuille(session, portefeuille_cree)


@router.get(
    "/investor/portefeuilles",
    response_model=Page[PortefeuilleResume],
    operation_id="listMyPortfolios",
    summary="Lister mes portefeuilles",
)
def lister_mes_portefeuilles_route(
    archive: bool | None = None,
    avec_position: bool | None = None,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> Page[PortefeuilleResume]:
    items, total = portfolio.lister_mes_portefeuilles(
        session,
        current_user.id,
        archive=archive,
        avec_position=avec_position,
        recherche=recherche,
        page=page,
        page_size=page_size,
    )
    return Page[PortefeuilleResume](
        items=items, page=page, page_size=page_size, total=total, pages=-(-total // page_size) or 1
    )


def _portefeuille_ou_404(session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID) -> Portefeuille:
    portefeuille = session.get(Portefeuille, portefeuille_id)
    if portefeuille is None or portefeuille.investisseur_id != investisseur_id:
        raise NotFoundError("Portefeuille introuvable.", code="portefeuille_introuvable")
    return portefeuille


@router.get(
    "/investor/portefeuilles/{portefeuille_id}",
    response_model=PortefeuilleDetail,
    operation_id="getPortfolioDetail",
    summary="Consulter le détail d'un portefeuille (positions, score agrégé, couverture)",
)
def consulter_portefeuille_route(
    portefeuille_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> PortefeuilleDetail:
    portefeuille = _portefeuille_ou_404(session, current_user.id, portefeuille_id)
    return portfolio.detail_portefeuille(session, portefeuille)


@router.patch(
    "/investor/portefeuilles/{portefeuille_id}",
    response_model=PortefeuilleResume,
    operation_id="renamePortfolio",
    summary="Renommer un portefeuille",
)
def renommer_portefeuille_route(
    portefeuille_id: uuid.UUID,
    payload: RenommerPortefeuilleRequest,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> PortefeuilleResume:
    portefeuille_renomme = portfolio.renommer_portefeuille(
        session, current_user.id, portefeuille_id, payload.nom
    )
    return portfolio.resume_portefeuille(session, portefeuille_renomme)


@router.post(
    "/investor/portefeuilles/{portefeuille_id}/archiver",
    response_model=PortefeuilleResume,
    operation_id="archivePortfolio",
    summary="Archiver un portefeuille",
)
def archiver_portefeuille_route(
    portefeuille_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> PortefeuilleResume:
    portefeuille_archive = portfolio.archiver_portefeuille(session, current_user.id, portefeuille_id)
    return portfolio.resume_portefeuille(session, portefeuille_archive)


@router.post(
    "/investor/portefeuilles/{portefeuille_id}/restaurer",
    response_model=PortefeuilleResume,
    operation_id="restorePortfolio",
    summary="Restaurer un portefeuille archivé",
)
def restaurer_portefeuille_route(
    portefeuille_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> PortefeuilleResume:
    portefeuille_restaure = portfolio.restaurer_portefeuille(session, current_user.id, portefeuille_id)
    return portfolio.resume_portefeuille(session, portefeuille_restaure)


@router.delete(
    "/investor/portefeuilles/{portefeuille_id}",
    status_code=204,
    operation_id="deletePortfolio",
    summary="Supprimer un portefeuille n'ayant jamais eu de position",
)
def supprimer_portefeuille_route(
    portefeuille_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> None:
    portfolio.supprimer_portefeuille(session, current_user.id, portefeuille_id)


@router.get(
    "/investor/portefeuilles/{portefeuille_id}/export",
    operation_id="exportPortfolio",
    summary="Exporter les positions d'un portefeuille au format CSV",
)
def exporter_portefeuille_route(
    portefeuille_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> Response:
    portefeuille = _portefeuille_ou_404(session, current_user.id, portefeuille_id)
    contenu_csv = portfolio.exporter_positions_csv(session, portefeuille)
    return Response(
        content=contenu_csv,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="portefeuille-{portefeuille_id}.csv"'},
    )


def _position_detail_apres_mutation(
    session: Session, portefeuille_id: uuid.UUID, position: PositionPortefeuille
) -> PositionDetail:
    portefeuille = session.get(Portefeuille, portefeuille_id)
    assert portefeuille is not None
    resume = portfolio.resume_portefeuille(session, portefeuille)
    return portfolio.position_detail(session, position, resume.montant_total)


@router.post(
    "/investor/portefeuilles/{portefeuille_id}/positions",
    response_model=PositionDetail,
    status_code=201,
    operation_id="addPosition",
    summary="Ajouter une position (ou renforcer, en ajoutant une nouvelle position sur la même entreprise)",
)
def ajouter_position_route(
    portefeuille_id: uuid.UUID,
    payload: AjouterPositionRequest,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> PositionDetail:
    position = portfolio.ajouter_position(session, current_user.id, portefeuille_id, payload)
    return _position_detail_apres_mutation(session, portefeuille_id, position)


@router.patch(
    "/investor/portefeuilles/{portefeuille_id}/positions/{position_id}",
    response_model=PositionDetail,
    operation_id="updatePosition",
    summary="Modifier une position encore planifiée",
)
def modifier_position_route(
    portefeuille_id: uuid.UUID,
    position_id: uuid.UUID,
    payload: ModifierPositionRequest,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> PositionDetail:
    position = portfolio.modifier_position(
        session, current_user.id, portefeuille_id, position_id, payload
    )
    return _position_detail_apres_mutation(session, portefeuille_id, position)


@router.post(
    "/investor/portefeuilles/{portefeuille_id}/positions/{position_id}/fermer",
    response_model=PositionDetail,
    operation_id="closePosition",
    summary="Fermer une position à durée ouverte",
)
def fermer_position_route(
    portefeuille_id: uuid.UUID,
    position_id: uuid.UUID,
    payload: FermerPositionRequest,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> PositionDetail:
    position = portfolio.fermer_position(
        session, current_user.id, portefeuille_id, position_id, payload.date_fin
    )
    return _position_detail_apres_mutation(session, portefeuille_id, position)


@router.delete(
    "/investor/portefeuilles/{portefeuille_id}/positions/{position_id}",
    status_code=204,
    operation_id="deletePosition",
    summary="Supprimer une position encore planifiée",
)
def supprimer_position_route(
    portefeuille_id: uuid.UUID,
    position_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.INVESTISSEUR)),
    session: Session = Depends(get_session),
) -> None:
    portfolio.supprimer_position(session, current_user.id, portefeuille_id, position_id)
